# Big Wins feed

A live screen of big wins on Solidicon games, pushed in real time through
Supabase. **Mock data**: brands and players are invented.

1. Run `setup.sql` in the Supabase SQL editor (table `big_wins` + Realtime).
2. `.env` with `SUPABASE_URL` and `SUPABASE_KEY` - here, or the one in
   `../supabase-check/` is used.
3. `py -3.11 mock_wins.py --backfill 40` - fills the last 6 hours, then adds a
   new win every 2-7 seconds until Ctrl+C. Also writes `config.js`.
4. Open `index.html` in a browser. Full screen (F11) for a TV.

The multiplier climbs the way a crash round does, `m^(t/T)`, so a x500 flies
visibly longer than a x25.

With real data, inserts must come from a server using the secret key; drop the
anon insert grant and policy in `setup.sql`.
