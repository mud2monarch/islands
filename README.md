# islands
Skip ads in podcasts

ffmpeg usage:
`ffmpeg -ss 00:01:22 -t 00:00:10 -i US_Economic_Outlook_and_Bond_Signals.mp3 -c copy opening_jingle.mp3`

### To operationalize:
[ ] Add idempotency to avoid reprocessing existing audio. Can use episode GUID.
[ ] Set up Cloudflare R2 on free tier
[ ] Clean up output and write (file, new RSS) to public bucket
[ ] Set up DO droplet to run with systemd
[ ] Set up retention policy. ~25MB per episode, 22 weekdays per month = 0.6 GB per month.
