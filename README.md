# Islands
Islands intelligently matches podcast mp3s against transcripts and reference clips and re-exports ad-free audio for personal use.

> [!IMPORTANT]
> WIP right now. Works for Bloomberg surveillance but not production ready.

Build a podcast as a directory in `reference/`
- Include audio clips and transcript references

# To Do
- [ ] Operationalize for BBS
- [x] Make flexible for other BB podcasts
- [x] Make generic over any podcast?
- [ ] Store state in DB
- [ ] Add R2 connections
- [ ] Add RSS writes

# Notes to self
ffmpeg usage:
`ffmpeg -ss 00:01:22 -t 00:00:10 -i US_Economic_Outlook_and_Bond_Signals.mp3 -c copy opening_jingle.mp3`

### To operationalize:
- [ ] Add idempotency to avoid reprocessing existing audio. Can use episode GUID.
- [ ] Set up Cloudflare R2 on free tier
- [ ] Clean up output and write (file, new RSS) to public bucket
- [ ] Set up DO droplet to run with systemd
- [ ] Set up retention policy. ~25MB per episode, 22 weekdays per month = 0.6 GB per month.
