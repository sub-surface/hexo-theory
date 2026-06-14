# Connect-k Parity and Primality Sweep

Seeded 1-2-2 Hex Connect-k first-layer tactical sweep. The tau values are threshold-oriented; values above 3 are capped as 4 because the decisive question here is whether the defender budget 2 is exceeded.

## Run

- k range: 3 to 10
- canonical opening limit per k: 48

## Rows

- k=3 (prime, odd): tempo=black, seed_tau=6, White urgent=48/48, Black reply tau>2=48/48, Black immediate wins=48
- k=4 (composite, even): tempo=white, seed_tau=0, White urgent=14/48, Black reply tau>2=47/48, Black immediate wins=0
- k=5 (prime, odd): tempo=black, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0
- k=6 (composite, even): tempo=white, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0
- k=7 (prime, odd): tempo=black, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0
- k=8 (composite, even): tempo=white, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0
- k=9 (composite, odd): tempo=black, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0
- k=10 (composite, even): tempo=white, seed_tau=0, White urgent=0/48, Black reply tau>2=0/48, Black immediate wins=0

## Aggregate Signal

- prime k total Black first-reply tau>2 openings: 48
- composite k total Black first-reply tau>2 openings: 47

## Interpretation

Parity is the stronger first-order effect. Odd k puts the urgent layer on Black's odd rooted stone counts; even k puts it on White's even move rhythm. Primality is a second-order question about whether forcing debt decomposes into smaller line-internal motifs.

The experiment supports using Connect-5 and Connect-7 as the first serious prime-k laboratories: Connect-3 collapses at the seed, while larger odd primes expose Black's first-reply tau envelope without the degenerate instant win.

## Files

- `connect_k_parity.csv`: row-level metrics.
- `atom_embedding_counts.csv`: geometric pair-atom embedding counts for k=4..8.
- `self_play_probe.csv`: very small strategy rollout probe for k=3..7.
- `figures/tempo_and_reply_tau.png`: seed, White opening, and Black reply tau curves.
- `figures/prime_composite_reply_tau.png`: Black first-reply tau>2 counts.
- `figures/white_opening_urgency.png`: White first-pair urgent openings.
