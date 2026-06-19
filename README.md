# Islands
Islands intelligently matches podcast mp3s against transcripts and reference clips and re-exports ad-free audio for personal use.

> [!IMPORTANT]
> WIP right now. Works e2e but some nice features + user guide still not ready.

Build a podcast as a directory in `reference/`
- Include audio clips and transcript references

# To Do
- [x] Operationalize for BBS
- [ ] Add a function that allows for manually redoing a podcast.
- [x] Make flexible for other BB podcasts
- [x] Make generic over any podcast?
- [x] Store state in DB
- [x] Add R2 connections
- [x] Add RSS writes
- [ ] Add R2 storage cleanup
- [ ] Set up on DO
- [ ] Make usable via cli
- [x] Add a date limiter to filter_n_episodes

# Notes to self
ffmpeg usage:
`ffmpeg -ss 00:01:22 -t 00:00:10 -i US_Economic_Outlook_and_Bond_Signals.mp3 -c copy opening_jingle.mp3`