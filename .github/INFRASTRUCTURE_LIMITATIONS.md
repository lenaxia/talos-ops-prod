## Infrastructure Limitations

The e2e workflow has been modified to include timeout configurations to handle GitHub Actions runner availability issues.

### Known Issues
- **Runner Acquisition Delays**: The workflow may experience delays in acquiring hosted runners, especially during high demand periods.
- **Concurrent Job Limitations**: Multiple jobs running simultaneously can strain available runner resources.
- **Timeouts**: All jobs now have a 60-minute timeout, and the workflow has a 180-minute overall timeout.

### Mitigation Strategies
- **Timeout Configuration**: Added `timeout-minutes: 60` to each job and `timeout-minutes: 180` at the workflow level.
- **Concurrent Job Management**: The workflow uses concurrency control to prevent multiple runs from interfering.
- **Monitoring**: We recommend monitoring GitHub Actions runner availability during peak usage times.

### Best Practices
- Avoid running large numbers of concurrent workflows during business hours.
- Consider using self-hosted runners for critical workflows.
- Monitor runner queue times and adjust timeouts accordingly.

This documentation will help maintainers understand the infrastructure constraints and make informed decisions about workflow design.