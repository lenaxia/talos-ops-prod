#!/bin/bash

# Verify all conversions
echo "Checking Middleware API versions:"
grep -r "apiVersion:" middlewares/

echo "Checking Ingress annotations:"
grep -r "traefik.io/router" ingresses/

echo "Checking for deprecated fields:"
grep -r "traefik.containo.us" middlewares/ ingresses/
