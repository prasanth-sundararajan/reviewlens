# sites.d: routes for other apps on this server

Caddy imports every `*.caddy` file in this folder into the ReviewLens site block, before
ReviewLens' own route. Use it to serve another app from the same domain without editing the
ReviewLens `Caddyfile`. These files are server-local (git-ignored).

Example: [LaunchScout](https://github.com/prasanth-sundararajan/launchscout) at
`/techstack/launchscout/` copies its `deploy/launchscout.caddy` here; then reload Caddy:

```bash
cp /opt/launchscout/deploy/launchscout.caddy /opt/reviewlens/sites.d/
docker exec reviewlens-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```
