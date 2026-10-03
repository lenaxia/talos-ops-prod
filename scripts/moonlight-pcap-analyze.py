#!/usr/bin/env python3
"""Offline analyzer for Moonlight/wolf session pcaps (item-4 debugging).

Parses a classic pcap (SLL/SLL2 linktypes, as written by `tcpdump -i any`),
extracts the RTSP/HTTP control exchange, and validates the RTP video stream
the way moonlight-common-c would receive it (RtpVideoQueue.c +
VideoDepacketizer.c semantics):

  - RTP sequence / timestamp / SSRC sanity
  - NV_VIDEO_PACKET fields: frameIndex, streamPacketIndex, fecInfo, flags
  - per-frame reassembly: SOF/EOF/CONTAINS_PIC_DATA pattern
  - Annex-B NAL visibility in the (unencrypted) payload after the frame header
  - SS_PING payload echo check on the video/audio ports

Usage: moonlight-pcap-analyze.py PCAP [client-ip]
Exit code 0 = stream structurally valid, 1 = problems found (see report).
"""
import struct
import sys
from collections import defaultdict

PCAP_MAGIC = {0xA1B2C3D4: ("<", 1_000), 0xD4C3B2A1: (">", 1_000),
              0xA1B23C4D: ("<", 1), 0x4D3CB2A1: (">", 1)}
SLL, SLL2 = 113, 276
# FLAG_EXTENSION is the RTP X bit (0x10 in the first RTP byte / 0x1000 in BE16)
FLAG_EXTENSION = 0x10
# NV_VIDEO_PACKET flags (moonlight-common-c src/Video.h)
FLAG_CONTAINS_PIC_DATA, FLAG_EOF, FLAG_SOF = 0x1, 0x2, 0x4


def parse_pcap(path):
    data = open(path, "rb").read()
    magic = struct.unpack("<I", data[:4])[0]
    if magic not in PCAP_MAGIC:
        sys.exit(f"not a classic pcap (magic {magic:#x})")
    endian, div = PCAP_MAGIC[magic]
    vmaj, vmin, tz, sig, snap, link = struct.unpack(endian + "HHiIII", data[4:24])
    off, pkts = 24, []
    while off + 16 <= len(data):
        ts, tus, caplen, wirelen = struct.unpack(endian + "IIII", data[off:off + 16])
        off += 16
        pkts.append((ts + tus / div / 1e6, data[off:off + caplen]))
        off += caplen
    return link, pkts


def l3_payload(pkt, link):
    """Return the IPv4 datagram bytes or None."""
    if link == SLL:      # 16B: proto BE at offset 14
        if len(pkt) < 16:
            return None
        proto, pkt = struct.unpack("!H", pkt[14:16])[0], pkt[16:]
    elif link == SLL2:   # 20B: proto BE at offset 0
        if len(pkt) < 20:
            return None
        proto, pkt = struct.unpack("!H", pkt[0:2])[0], pkt[20:]
    elif link in (1,):   # raw Ethernet
        if len(pkt) < 14:
            return None
        proto, pkt = struct.unpack("!H", pkt[12:14])[0], pkt[14:]
    else:
        sys.exit(f"unsupported linktype {link}; convert with tcpdump -w or editcap")
    return pkt if proto == 0x0800 else None


def parse_udp(pkt):
    ihl = (pkt[0] & 0xF) * 4
    if (pkt[0] >> 4) != 4 or pkt[9] != 17:
        return None
    src = ".".join(map(str, pkt[12:16]))
    dst = ".".join(map(str, pkt[16:20]))
    sport, dport, _, ulen = struct.unpack("!HHHH", pkt[ihl:ihl + 8])
    return src, sport, dst, dport, pkt[ihl + 8:ihl + 8 + ulen - 8]


def parse_tcp(pkt):
    ihl = (pkt[0] & 0xF) * 4
    if (pkt[0] >> 4) != 4 or pkt[9] != 6:
        return None
    src = ".".join(map(str, pkt[12:16]))
    dst = ".".join(map(str, pkt[16:20]))
    sport, dport = struct.unpack("!HH", pkt[ihl:ihl + 4])
    off_flags = struct.unpack("!H", pkt[ihl + 12:ihl + 14])[0]
    doff = (off_flags >> 12) * 4
    return src, sport, dst, dport, pkt[ihl + doff:]


def rtp_video_parse(payload):
    """Parse one video packet -> dict or None.

    Wire format (moonlight-common-c src/Video.h):
      RTP(12) [+4 if X bit] + NV_VIDEO_PACKET{spi LE32, frameIndex LE32,
      flags u8, extraFlags u8, multiFecFlags u8, multiFecBlocks u8,
      fecInfo LE32}
    """
    if len(payload) < 12 + 4 + 16:
        return None
    b0, pt_flags, seq, ts, ssrc = struct.unpack("!BBHII", payload[:12])
    if b0 >> 6 != 2:
        return None
    dataoff = 12 + (4 if (b0 & FLAG_EXTENSION) else 0)
    nv = payload[dataoff:]
    spi, frame_index = struct.unpack("<II", nv[:8])
    flags, extra_flags, mf_flags, mf_blocks = nv[8], nv[9], nv[10], nv[11]
    fec_info, = struct.unpack("<I", nv[12:16])
    return dict(seq=seq, rtp_ts=ts, ssrc=ssrc, x=bool(b0 & FLAG_EXTENSION),
                pt=pt_flags & 0x7F, spi=spi & 0xFFFFFF, frame=frame_index,
                fec=fec_info, flags=flags, extra=extra_flags,
                mf_blocks=mf_blocks, body=nv[16:], dataoff=dataoff)


def fec_decode(fec):
    data_pkts = (fec >> 22) & 0x3FF
    fec_idx = (fec >> 12) & 0x3FF
    fec_pct = (fec >> 4) & 0xFF
    return data_pkts, fec_idx, fec_pct


def is_annexb_start(b, off):
    if b[off:off + 2] != b"\x00\x00":
        return 0
    if b[off + 2:off + 3] == b"\x01":
        return 3
    if b[off + 2:off + 4] == b"\x00\x01" and len(b) > off + 4:
        return 4
    return 0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    link, pkts = parse_pcap(sys.argv[1])
    t0 = pkts[0][0] if pkts else 0
    flows = defaultdict(int)
    video_out, video_in, audio_out, audio_in = [], [], [], []
    http_out, rtsp_out = {47989: [], 48010: []}, {48010: []}
    problems, notes = [], []

    for t, pkt in pkts:
        ip = l3_payload(pkt, link)
        if ip is None:
            continue
        udp = parse_udp(ip)
        if udp:
            src, sp, dst, dp, pl = udp
            flows[(src, sp, dst, dp)] += 1
            if dp in (47989, 48010):  # unlikely (tcp), skip
                pass
            if sp == 48100:
                video_out.append((t, pl))
            elif dp == 48100:
                video_in.append((t, pl))
            elif sp == 48200:
                audio_out.append((t, pl))
            elif dp == 48200:
                audio_in.append((t, pl))
            continue
        tcp = parse_tcp(ip)
        if tcp:
            src, sp, dst, dp, pl = tcp
            if pl and dp == 47989:
                http_out[47989].append((t, pl))
            if pl and dp == 48010:
                rtsp_out[48010].append((t, pl))

    print(f"== pcap: {len(pkts)} packets, linktype {link}, {len(flows)} UDP flows ==")
    for (src, sp, dst, dp), n in sorted(flows.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {src}:{sp} -> {dst}:{dp}  {n} pkts")

    # HTTP: find launch URL (rikey) and any appid
    http_blob = b"".join(p for _, p in http_out[47989])
    launch, rikey, rikeyid = None, None, None
    for line in http_blob.decode("latin1").splitlines():
        if line.startswith("GET /launch"):
            launch = line.strip()
            for kv in line.split("?")[-1].split("&"):
                if kv.startswith("rikey="):
                    rikey = kv[6:].strip()
                if kv.startswith("rikeyid="):
                    rikeyid = kv[8:].strip()
    print(f"\n== HTTP 47989: launch URL: {'FOUND' if launch else 'not captured'}")
    if launch:
        print(f"   {launch[:120]}...")
        print(f"   rikey: {'captured (' + str(len(rikey)) + ' hex chars)' if rikey else 'absent'}"
              f"  rikeyid: {rikeyid or 'absent'}")

    # RTSP: ping payload + encryption feature lines
    rtsp_text = b"".join(p for _, p in rtsp_out[48010]).decode("latin1")
    for tag in ("X-SS-Ping-Payload", "x-ss-encryption", "a=control", "SESSION"):
        hits = [l.strip() for l in rtsp_text.splitlines() if tag.lower() in l.lower()]
        for h in hits[:4]:
            print(f"   RTSP {tag}: {h[:100]}")

    # Pings: client -> 48100/48200 small plaintext pkts; echo scan outbound
    for label, inbound, outbound in (("video", video_in, video_out),
                                     ("audio", audio_in, audio_out)):
        pings = [(t, p) for t, p in inbound if len(p) <= 32]
        echoed = 0
        out_blob = {bytes(p[4:20]) for _, p in outbound if len(p) >= 20}
        for t, p in pings:
            if p[4:20] in out_blob:
                echoed += 1
        if pings:
            print(f"\n== {label} pings: {len(pings)} inbound, {echoed} echoed back")
            if echoed == 0:
                problems.append(f"no {label} ping replies from host (moonlight clients "
                                f"expect payload echo; sunshine implements it)")
        sample = pings[0][1] if pings else b""
        print(f"   sample inbound ping ({len(sample)}B): {sample[4:20]!r}")

    # Video RTP analysis
    if not video_out:
        sys.exit("no outbound video packets on :48100 captured")
    parsed = []
    for t, p in video_out:
        r = rtp_video_parse(p)
        if r:
            r["t"] = t
            parsed.append(r)
    print(f"\n== video RTP: {len(video_out)} pkts, {len(parsed)} parsed ==")
    if len(parsed) < len(video_out):
        problems.append(f"{len(video_out) - len(parsed)} video packets failed RTP/NV parse")

    seqs = [r["seq"] for r in parsed]
    gaps = [(a, b) for a, b in zip(seqs, seqs[1:]) if b != (a + 1) & 0xFFFF]
    print(f"   seq: {seqs[0]}..{seqs[-1]}, discontinuities: {len(gaps)} {gaps[:4]}")
    if gaps:
        problems.append(f"RTP seq discontinuities: {len(gaps)} (first: {gaps[:3]})")
    ss = {r["ssrc"] for r in parsed}
    pts = {r["pt"] for r in parsed}
    print(f"   ssrc: {[hex(s) for s in ss]}  PT: {sorted(pts)}  X-bit: "
          f"{sum(r['x'] for r in parsed)}/{len(parsed)}")
    if len(ss) != 1:
        problems.append(f"multiple SSRCs: {ss}")

    frames = defaultdict(list)
    for r in parsed:
        frames[r["frame"]].append(r)
    fnums = sorted(frames)
    print(f"   frames: {len(fnums)} ({fnums[0]}..{fnums[-1]}), "
          f"non-consecutive: {[ (a, b) for a, b in zip(fnums, fnums[1:]) if b != a + 1 ][:5]}")
    fps = len(fnums) / (parsed[-1]["t"] - parsed[0]["t"]) if len(parsed) > 1 else 0
    print(f"   effective fps: {fps:.1f}")

    # Data vs parity: within each frameIndex group, the first fecInfo.dataPackets
    # sequence numbers are data, the rest are parity (client semantics)
    data_rows, parity_rows = [], []
    for f in fnums:
        pk = sorted(frames[f], key=lambda r: r["seq"])
        d0, _, _ = fec_decode(pk[0]["fec"])
        data_rows += pk[:d0]
        parity_rows += pk[d0:]
    spis = [r["spi"] for r in data_rows]
    spi_nonmono = sum(1 for a, b in zip(spis, spis[1:]) if b <= a)
    print(f"   data pkts: {len(data_rows)}, parity pkts: {len(parity_rows)}")
    print(f"   data-packet spi: {spis[0]}..{spis[-1]}, non-monotonic: {spi_nonmono}")
    if spi_nonmono:
        problems.append("data-packet streamPacketIndex went backwards "
                        "(depacketizer would flag corrupt frames)")

    # Per-frame flag pattern + fecInfo (data packets only; parity is
    # classified by sequence position and may carry garbage headers)
    bad_flags, fec_reported, idr_frames = 0, set(), []
    for f in fnums:
        pk = [r for r in frames[f] if r["flags"] & (FLAG_SOF | FLAG_EOF)]
        first, last = pk[0], pk[-1]
        if not (first["flags"] & FLAG_SOF and last["flags"] & FLAG_EOF):
            bad_flags += 1
        fec_reported.add(fec_decode(pk[0]["fec"]))
        body = first["body"]
        if body[:1] in (b"\x01", b"\x81") and len(body) > 3 and body[3] == 2:
            idr_frames.append(f)
    if bad_flags:
        problems.append(f"{bad_flags}/{len(fnums)} frames lack SOF..EOF pattern")
    print(f"   frames missing SOF/EOF pattern: {bad_flags}")
    print(f"   fecInfo (dataPkts,fecIdx,fec%): {sorted(fec_reported)[:6]}")
    print(f"   IDR frames (frame-header type=2): {len(idr_frames)} "
          f"{idr_frames[:12]}")
    if fnums and fnums[0] == 0:
        problems.append("frameIndex starts at 0: moonlight-common-c initializes "
                        "currentFrameNumber/nextFrameNumber=1 and drops frame 0 "
                        "(the first IDR) via isBefore16/32")
    ts_nonzero = sum(1 for r in parsed if r["rtp_ts"])
    if ts_nonzero == 0:
        notes.append("all RTP timestamps are 0 (client synthesizes PTS; "
                     "tolerated but nonconformant)")
    n_parity = sum(1 for r in parsed if not (r["flags"] & (FLAG_SOF | FLAG_EOF)))
    parity_bad_flags = sum(1 for r in parsed
                           if not (r["flags"] & (FLAG_SOF | FLAG_EOF))
                           and r["flags"] & ~(FLAG_SOF | FLAG_EOF | FLAG_CONTAINS_PIC_DATA))
    if parity_bad_flags:
        notes.append(f"{n_parity} parity packets, {parity_bad_flags} with garbage "
                     f"flags/spi (client classifies parity by seq position; ignored)")

    # Frame header + Annex-B visibility on first frame's first packet
    f0 = frames[fnums[0]][0]
    body = f0["body"]
    print(f"\n   first video pkt (frame {fnums[0]}, flags={f0['flags']:#x}):")
    print(f"     body[{len(body)}B] head: {body[:24].hex(' ')}")
    hdrlen = 8 if body[:1] in (b"\x01", b"\x81") else 0
    htype = body[3] if hdrlen else None
    print(f"     frame header: {'8B type=' + str(htype) if hdrlen == 8 else 'other/none'}"
          f" (types: 1=P 2=IDR 4=intraRefresh 5=RFI 104=sunshine)")
    startlen = is_annexb_start(body, hdrlen)
    if startlen:
        nal = body[hdrlen + startlen]
        h264_nal, hevc_nal = nal & 0x1F, (nal & 0x7E) >> 1
        print(f"     AnnexB start ({startlen}B) + NAL byte {nal:#04x} "
              f"(h264 type={h264_nal}, hevc type={hevc_nal})")
        if h264_nal in (7, 8, 5, 6, 9):
            print("     => looks like a valid H.264 parameter/slice NAL: payload is "
                  "NOT encrypted (or encryption is off)")
        elif hevc_nal in (32, 33, 34, 19, 20, 35, 39):
            print(f"     => HEVC NAL {hevc_nal} (32=VPS 33=SPS 34=PPS 19/20=IDR "
                  f"slice): payload is NOT encrypted")
        else:
            notes.append(f"NAL byte {nal:#04x} not a typical first NAL (7/8/5/6/9) — "
                         f"payload may be encrypted")
    else:
        notes.append("no AnnexB start code after frame header — payload likely encrypted "
                     "(or decode assumption wrong)")
    if rikey and not startlen:
        notes.append(f"rikey available ({len(rikey)} hex chars): AES decrypt pass needed "
                     f"to rule out key/payload corruption")

    print("\n== PROBLEMS ==" if problems else "\n== NO STRUCTURAL PROBLEMS FOUND ==")
    for p in problems:
        print(f"  - {p}")
    print("== NOTES ==")
    for n in notes:
        print(f"  - {n}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
