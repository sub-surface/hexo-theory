//! Hex Threat Manifold Microscope
//!
//! A zero-dependency Rust implementation of an ultraminimal experiment for
//! infinite Hex Connect-6 / HeXO-style play:
//!
//! - Axial Eisenstein-like coordinates on the hex grid.
//! - 1-2-2 rule support in the board model.
//! - Length-6 wins along the three hex axes.
//! - Scalar board/threat fields.
//! - Pair-move features on Sym^2(H).
//! - Tiny PCA implementation for a 2D latent "threat manifold" SVG.
//! - OOM-aware candidate pruning: enumerate cells, then only pair top candidate cells.
//!
//! Build:
//!     cargo run --release -- --radius 8 --candidates 160 --seed 7 --out out
//!
//! Output:
//!     out/board.svg
//!     out/threat_heatmap.svg
//!     out/pair_latent.svg
//!     out/cells.csv
//!     out/pairs.csv
//!     out/summary.md
//!
//! This is deliberately compact but not toyish: the tactical features are local,
//! interpretable, and fast enough to iterate on large bounded windows.

use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::env;
use std::f64::consts::PI;
use std::fs::{self, File};
use std::hash::{Hash, Hasher};
use std::io::{BufWriter, Write};
use std::path::PathBuf;

// -----------------------------
// Basic data structures
// -----------------------------

#[derive(Clone, Copy, Debug, Eq)]
struct Ax {
    q: i32,
    r: i32,
}

impl Ax {
    const fn new(q: i32, r: i32) -> Self {
        Self { q, r }
    }

    fn add(self, other: Ax) -> Ax {
        Ax::new(self.q + other.q, self.r + other.r)
    }

    fn sub(self, other: Ax) -> Ax {
        Ax::new(self.q - other.q, self.r - other.r)
    }

    fn scale(self, k: i32) -> Ax {
        Ax::new(self.q * k, self.r * k)
    }

    fn dist(self, other: Ax) -> i32 {
        let dq = self.q - other.q;
        let dr = self.r - other.r;
        let ds = -dq - dr;
        dq.abs().max(dr.abs()).max(ds.abs())
    }

    fn norm(self) -> i32 {
        self.dist(Ax::new(0, 0))
    }

    fn key(self) -> String {
        format!("{},{}", self.q, self.r)
    }
}

impl PartialEq for Ax {
    fn eq(&self, other: &Self) -> bool {
        self.q == other.q && self.r == other.r
    }
}
impl Hash for Ax {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.q.hash(state);
        self.r.hash(state);
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Stone {
    Empty,
    Black,
    White,
}

impl Stone {
    fn opponent(self) -> Stone {
        match self {
            Stone::Black => Stone::White,
            Stone::White => Stone::Black,
            Stone::Empty => Stone::Empty,
        }
    }

    fn sign(self) -> i32 {
        match self {
            Stone::Black => 1,
            Stone::White => -1,
            Stone::Empty => 0,
        }
    }

    fn name(self) -> &'static str {
        match self {
            Stone::Black => "black",
            Stone::White => "white",
            Stone::Empty => "empty",
        }
    }
}

#[derive(Clone)]
struct Board {
    stones: HashMap<Ax, Stone>,
    move_number: usize,
}

impl Board {
    fn new() -> Self {
        Self {
            stones: HashMap::new(),
            move_number: 0,
        }
    }

    fn get(&self, p: Ax) -> Stone {
        *self.stones.get(&p).unwrap_or(&Stone::Empty)
    }

    fn is_empty(&self, p: Ax) -> bool {
        self.get(p) == Stone::Empty
    }

    fn place(&mut self, p: Ax, s: Stone) -> bool {
        if s == Stone::Empty || !self.is_empty(p) {
            return false;
        }
        self.stones.insert(p, s);
        true
    }

    fn place_many(&mut self, ps: &[Ax], s: Stone) -> bool {
        let expected = if self.move_number == 0 { 1 } else { 2 };
        if ps.len() != expected {
            return false;
        }
        let mut seen = HashSet::new();
        for &p in ps {
            if !seen.insert(p) || !self.is_empty(p) {
                return false;
            }
        }
        for &p in ps {
            self.place(p, s);
        }
        self.move_number += 1;
        true
    }

    fn with_pair(&self, a: Ax, b: Ax, color: Stone) -> Board {
        let mut nb = self.clone();
        nb.place(a, color);
        nb.place(b, color);
        nb
    }

    fn with_one(&self, a: Ax, color: Stone) -> Board {
        let mut nb = self.clone();
        nb.place(a, color);
        nb
    }

    fn occupied_bounds_radius(&self) -> i32 {
        self.stones.keys().map(|p| p.norm()).max().unwrap_or(0)
    }

    fn has_win(&self, color: Stone) -> bool {
        for (&p, &s) in self.stones.iter() {
            if s != color {
                continue;
            }
            for &d in DIRS.iter() {
                // Only count each segment once from its minimal endpoint.
                if self.get(p.sub(d)) == color {
                    continue;
                }
                let mut k = 0;
                while self.get(p.add(d.scale(k))) == color {
                    k += 1;
                    if k >= 6 {
                        return true;
                    }
                }
            }
        }
        false
    }
}

const DIRS: [Ax; 3] = [Ax::new(1, 0), Ax::new(0, 1), Ax::new(1, -1)];

// -----------------------------
// Configuration and CLI
// -----------------------------

#[derive(Clone, Debug)]
struct Config {
    radius: i32,
    candidates: usize,
    seed: u64,
    out: PathBuf,
    color: Stone,
    position: String,
    kernel_sigma: f64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            radius: 8,
            candidates: 160,
            seed: 7,
            out: PathBuf::from("hex_threat_out"),
            color: Stone::Black,
            position: "fork".to_string(),
            kernel_sigma: 2.25,
        }
    }
}

fn parse_args() -> Config {
    let mut cfg = Config::default();
    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--radius" | "-r" => {
                i += 1;
                cfg.radius = args.get(i).and_then(|x| x.parse().ok()).unwrap_or(cfg.radius);
            }
            "--candidates" | "-c" => {
                i += 1;
                cfg.candidates = args.get(i).and_then(|x| x.parse().ok()).unwrap_or(cfg.candidates);
            }
            "--seed" | "-s" => {
                i += 1;
                cfg.seed = args.get(i).and_then(|x| x.parse().ok()).unwrap_or(cfg.seed);
            }
            "--out" | "-o" => {
                i += 1;
                cfg.out = args.get(i).map(PathBuf::from).unwrap_or(cfg.out.clone());
            }
            "--color" => {
                i += 1;
                let c = args.get(i).map(|x| x.as_str()).unwrap_or("black");
                cfg.color = if c.eq_ignore_ascii_case("white") {
                    Stone::White
                } else {
                    Stone::Black
                };
            }
            "--position" => {
                i += 1;
                cfg.position = args.get(i).cloned().unwrap_or_else(|| cfg.position.clone());
            }
            "--sigma" => {
                i += 1;
                cfg.kernel_sigma = args.get(i).and_then(|x| x.parse().ok()).unwrap_or(cfg.kernel_sigma);
            }
            "--help" | "-h" => {
                print_help_and_exit();
            }
            other => {
                eprintln!("Unknown argument: {other}");
                print_help_and_exit();
            }
        }
        i += 1;
    }
    cfg
}

fn print_help_and_exit() -> ! {
    println!(
        "\
Hex Threat Manifold Microscope

Usage:
  cargo run --release -- --radius 8 --candidates 160 --seed 7 --out out

Options:
  --radius, -r       finite observation radius around origin [default: 8]
  --candidates, -c   top empty cells retained before pair enumeration [default: 160]
  --seed, -s         seed for procedural position [default: 7]
  --out, -o          output directory [default: hex_threat_out]
  --color            black or white, side to evaluate [default: black]
  --position         fork, race, random, empty [default: fork]
  --sigma            kernel width for smooth field layer [default: 2.25]

Notes:
  Infinite Hex Connect-6 is sampled through a bounded observation window.
  Candidate pruning is intentional: full pair space is Θ(N²), so this is the
  first OOM guardrail and a model of tactical attention."
    );
    std::process::exit(0);
}

// -----------------------------
// Small RNG, no dependencies
// -----------------------------

#[derive(Clone)]
struct Rng64 {
    state: u64,
}

impl Rng64 {
    fn new(seed: u64) -> Self {
        let s = if seed == 0 { 0x9E3779B97F4A7C15 } else { seed };
        Self { state: s }
    }

    fn next_u64(&mut self) -> u64 {
        // xorshift64*
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }

    fn f64(&mut self) -> f64 {
        let x = self.next_u64() >> 11;
        (x as f64) * (1.0 / ((1u64 << 53) as f64))
    }

    fn usize(&mut self, n: usize) -> usize {
        if n == 0 {
            0
        } else {
            (self.next_u64() as usize) % n
        }
    }
}

// -----------------------------
// Hex geometry and board setup
// -----------------------------

fn hex_disk(radius: i32) -> Vec<Ax> {
    let mut v = Vec::new();
    for q in -radius..=radius {
        for r in -radius..=radius {
            let p = Ax::new(q, r);
            if p.norm() <= radius {
                v.push(p);
            }
        }
    }
    v
}

fn axial_to_xy(p: Ax, scale: f64) -> (f64, f64) {
    // pointy-top axial layout
    let x = scale * (3.0_f64.sqrt() * (p.q as f64 + p.r as f64 / 2.0));
    let y = scale * (1.5 * p.r as f64);
    (x, y)
}

fn hex_polygon(cx: f64, cy: f64, size: f64) -> String {
    let mut pts = Vec::with_capacity(6);
    for i in 0..6 {
        let angle = PI / 180.0 * (60.0 * i as f64 - 30.0);
        pts.push(format!("{:.3},{:.3}", cx + size * angle.cos(), cy + size * angle.sin()));
    }
    pts.join(" ")
}

fn make_position(kind: &str, seed: u64) -> Board {
    let mut b = Board::new();
    let mut rng = Rng64::new(seed);

    match kind {
        "empty" => {}
        "race" => {
            // Two players have live structures on crossing axes.
            let black = [Ax::new(-3, 0), Ax::new(-2, 0), Ax::new(-1, 0), Ax::new(1, 0),
                         Ax::new(2, 0), Ax::new(0, -2), Ax::new(0, -1)];
            let white = [Ax::new(-2, 2), Ax::new(-1, 1), Ax::new(1, -1), Ax::new(2, -2),
                         Ax::new(3, -3), Ax::new(-1, -2), Ax::new(0, -2)];
            for p in black { b.place(p, Stone::Black); }
            for p in white { b.place(p, Stone::White); }
            b.move_number = 8;
        }
        "random" => {
            let cells = hex_disk(5);
            for _ in 0..26 {
                let p = cells[rng.usize(cells.len())];
                let c = if rng.f64() < 0.5 { Stone::Black } else { Stone::White };
                b.place(p, c);
            }
            b.move_number = 13;
        }
        "fork" | _ => {
            // A deliberately suggestive Hex Connect-6 position:
            // Black has almost-lines on multiple axes, but not a direct win.
            // White has enough material to create blocking obligations.
            let black = [
                Ax::new(-4, 0), Ax::new(-3, 0), Ax::new(-2, 0), Ax::new(0, 0),
                Ax::new(1, -1), Ax::new(2, -2), Ax::new(3, -3),
                Ax::new(0, -3), Ax::new(0, -2), Ax::new(0, 1),
                Ax::new(-2, 2), Ax::new(-1, 1),
            ];
            let white = [
                Ax::new(-1, 0), Ax::new(2, 0),
                Ax::new(0, -1), Ax::new(0, 2),
                Ax::new(1, -2), Ax::new(2, -3),
                Ax::new(-3, 1), Ax::new(-2, 1),
                Ax::new(1, 1), Ax::new(2, 1),
            ];
            for p in black { b.place(p, Stone::Black); }
            for p in white { b.place(p, Stone::White); }
            b.move_number = 11;
        }
    }

    b
}

// -----------------------------
// Tactical feature computation
// -----------------------------

#[derive(Clone, Debug)]
struct CellFeature {
    p: Ax,
    own_live_score: f64,
    opp_live_score: f64,
    own_immediate_wins: i32,
    opp_immediate_wins: i32,
    fork_potential: f64,
    smooth_field: f64,
    candidate_score: f64,
}

#[derive(Clone, Debug)]
struct PairFeature {
    a: Ax,
    b: Ax,
    own_gain: f64,
    block_gain: f64,
    synergy: f64,
    distance: f64,
    immediate_win: bool,
    immediate_block: bool,
    post_obligations: i32,
    over_two_obligations: i32,
    latent_x: f64,
    latent_y: f64,
    class_name: String,
}

fn live_line_stats(board: &Board, p: Ax, color: Stone) -> (f64, i32) {
    // Sum over all length-6 segments containing p along the three axes.
    // A segment is live for color if it contains no opponent stones.
    // Score weights longer own runs sharply.
    let mut score = 0.0;
    let mut immediate = 0;

    for &d in DIRS.iter() {
        for offset in 0..6 {
            let start = p.sub(d.scale(offset));
            let mut own = 0;
            let mut opp = 0;
            let mut empties = 0;

            for k in 0..6 {
                let x = start.add(d.scale(k));
                let s = if x == p { color } else { board.get(x) };
                if s == color {
                    own += 1;
                } else if s == color.opponent() {
                    opp += 1;
                } else {
                    empties += 1;
                }
            }

            if opp == 0 {
                // The +1 is already included because p is hypothetically occupied.
                // 5 own stones after placement means p completes six.
                if own >= 6 {
                    immediate += 1;
                }
                let base = match own {
                    0 => 0.0,
                    1 => 0.4,
                    2 => 1.0,
                    3 => 3.0,
                    4 => 9.0,
                    5 => 27.0,
                    _ => 100.0,
                };
                // Fewer empties means more urgent.
                score += base / (1.0 + empties as f64 * 0.15);
            }
        }
    }

    (score, immediate)
}

fn immediate_threat_cells(board: &Board, color: Stone, cells: &[Ax]) -> Vec<Ax> {
    let mut out = Vec::new();
    for &p in cells {
        if !board.is_empty(p) {
            continue;
        }
        let (_, wins) = live_line_stats(board, p, color);
        if wins > 0 {
            out.push(p);
        }
    }
    out
}

fn smooth_kernel_field(board: &Board, p: Ax, sigma: f64) -> f64 {
    let mut acc = 0.0;
    let denom = 2.0 * sigma * sigma;
    for (&spos, &stone) in board.stones.iter() {
        let d = p.dist(spos) as f64;
        let k = (-(d * d) / denom).exp();
        acc += k * stone.sign() as f64;
    }
    acc
}

fn cell_features(board: &Board, cells: &[Ax], color: Stone, sigma: f64) -> Vec<CellFeature> {
    let opp = color.opponent();
    let mut feats = Vec::new();

    for &p in cells {
        if !board.is_empty(p) {
            continue;
        }
        let (own_score, own_wins) = live_line_stats(board, p, color);
        let (opp_score, opp_wins) = live_line_stats(board, p, opp);
        let smooth = smooth_kernel_field(board, p, sigma);
        // Fork potential: product-like pressure from own creation and opponent block need.
        let fork = (own_score.sqrt() + 0.25) * (1.0 + own_wins as f64);
        let candidate = own_score + 1.35 * opp_score + 80.0 * (own_wins + opp_wins) as f64 + 0.2 * fork;

        feats.push(CellFeature {
            p,
            own_live_score: own_score,
            opp_live_score: opp_score,
            own_immediate_wins: own_wins,
            opp_immediate_wins: opp_wins,
            fork_potential: fork,
            smooth_field: smooth,
            candidate_score: candidate,
        });
    }

    feats.sort_by(|a, b| b.candidate_score.partial_cmp(&a.candidate_score).unwrap_or(Ordering::Equal));
    feats
}

fn same_axis_distance(a: Ax, b: Ax) -> Option<(usize, i32)> {
    let diff = b.sub(a);
    for (i, d) in DIRS.iter().enumerate() {
        // b-a = k*d
        if d.q != 0 {
            if diff.q % d.q == 0 {
                let k = diff.q / d.q;
                if d.r * k == diff.r {
                    return Some((i, k.abs()));
                }
            }
        } else if d.r != 0 && diff.r % d.r == 0 {
            let k = diff.r / d.r;
            if d.q * k == diff.q {
                return Some((i, k.abs()));
            }
        }
    }
    None
}

fn pair_synergy(board: &Board, a: Ax, b: Ax, color: Stone) -> f64 {
    let mut s = 0.0;
    if let Some((_axis, gap)) = same_axis_distance(a, b) {
        if gap <= 5 {
            s += 15.0 / (gap as f64);
        }
    }

    // Superadditive effect: how much the second stone improves after first stone exists.
    let b1 = board.with_one(a, color);
    let (b_alone, _) = live_line_stats(board, b, color);
    let (b_after, _) = live_line_stats(&b1, b, color);
    let b2 = board.with_one(b, color);
    let (a_alone, _) = live_line_stats(board, a, color);
    let (a_after, _) = live_line_stats(&b2, a, color);
    s += (b_after - b_alone).max(0.0) + (a_after - a_alone).max(0.0);
    s
}

fn classify_pair(pf: &PairFeature) -> String {
    if pf.immediate_win {
        "win".to_string()
    } else if pf.post_obligations > 2 {
        "fork".to_string()
    } else if pf.immediate_block {
        "block".to_string()
    } else if pf.own_gain + pf.synergy > 60.0 {
        "pressure".to_string()
    } else {
        "quiet".to_string()
    }
}

fn pair_features(
    board: &Board,
    candidates: &[CellFeature],
    all_cells: &[Ax],
    color: Stone,
) -> Vec<PairFeature> {
    let opp = color.opponent();
    let mut out = Vec::new();

    for i in 0..candidates.len() {
        for j in (i + 1)..candidates.len() {
            let a = candidates[i].p;
            let b = candidates[j].p;
            if a == b || !board.is_empty(a) || !board.is_empty(b) {
                continue;
            }

            let b2 = board.with_pair(a, b, color);
            let own_gain = candidates[i].own_live_score + candidates[j].own_live_score;
            let block_gain = candidates[i].opp_live_score + candidates[j].opp_live_score;
            let synergy = pair_synergy(board, a, b, color);
            let immediate_win = b2.has_win(color);
            let opp_before = immediate_threat_cells(board, opp, all_cells).len();
            let opp_after_blocking = {
                let bb = board.with_pair(a, b, color);
                immediate_threat_cells(&bb, opp, all_cells).len()
            };
            let immediate_block = opp_before > 0 && opp_after_blocking < opp_before;

            // Obligations after this pair: how many immediate winning cells will color have?
            // If > 2, opponent's next two stones cannot cover all of them.
            let obligations = immediate_threat_cells(&b2, color, all_cells).len() as i32;
            let over_two = (obligations - 2).max(0);

            let mut pf = PairFeature {
                a,
                b,
                own_gain,
                block_gain,
                synergy,
                distance: a.dist(b) as f64,
                immediate_win,
                immediate_block,
                post_obligations: obligations,
                over_two_obligations: over_two,
                latent_x: 0.0,
                latent_y: 0.0,
                class_name: String::new(),
            };
            pf.class_name = classify_pair(&pf);
            out.push(pf);
        }
    }

    out
}

// -----------------------------
// Tiny PCA implementation
// -----------------------------

fn feature_matrix(pairs: &[PairFeature]) -> Vec<Vec<f64>> {
    pairs.iter().map(|p| {
        vec![
            p.own_gain.ln_1p(),
            p.block_gain.ln_1p(),
            p.synergy.ln_1p(),
            p.distance,
            if p.immediate_win { 1.0 } else { 0.0 },
            if p.immediate_block { 1.0 } else { 0.0 },
            p.post_obligations as f64,
            p.over_two_obligations as f64,
        ]
    }).collect()
}

fn normalize_columns(x: &mut [Vec<f64>]) -> (Vec<f64>, Vec<f64>) {
    if x.is_empty() {
        return (Vec::new(), Vec::new());
    }
    let n = x.len();
    let d = x[0].len();
    let mut mean = vec![0.0; d];
    let mut std = vec![0.0; d];

    for row in x.iter() {
        for k in 0..d {
            mean[k] += row[k];
        }
    }
    for k in 0..d {
        mean[k] /= n as f64;
    }
    for row in x.iter() {
        for k in 0..d {
            let z = row[k] - mean[k];
            std[k] += z * z;
        }
    }
    for k in 0..d {
        std[k] = (std[k] / (n as f64).max(1.0)).sqrt().max(1e-9);
    }
    for row in x.iter_mut() {
        for k in 0..d {
            row[k] = (row[k] - mean[k]) / std[k];
        }
    }
    (mean, std)
}

fn covariance(x: &[Vec<f64>]) -> Vec<Vec<f64>> {
    if x.is_empty() {
        return Vec::new();
    }
    let n = x.len();
    let d = x[0].len();
    let mut c = vec![vec![0.0; d]; d];
    for row in x {
        for i in 0..d {
            for j in i..d {
                c[i][j] += row[i] * row[j];
            }
        }
    }
    for i in 0..d {
        for j in i..d {
            c[i][j] /= (n as f64 - 1.0).max(1.0);
            c[j][i] = c[i][j];
        }
    }
    c
}

fn mat_vec(a: &[Vec<f64>], v: &[f64]) -> Vec<f64> {
    let d = v.len();
    let mut out = vec![0.0; d];
    for i in 0..d {
        let mut s = 0.0;
        for j in 0..d {
            s += a[i][j] * v[j];
        }
        out[i] = s;
    }
    out
}

fn norm(v: &[f64]) -> f64 {
    v.iter().map(|x| x * x).sum::<f64>().sqrt()
}

fn dot(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

fn power_iteration(a: &[Vec<f64>], seed: u64, iterations: usize) -> (f64, Vec<f64>) {
    let d = a.len();
    let mut rng = Rng64::new(seed);
    let mut v = (0..d).map(|_| rng.f64() - 0.5).collect::<Vec<_>>();
    let mut nv = norm(&v).max(1e-12);
    for x in v.iter_mut() {
        *x /= nv;
    }

    for _ in 0..iterations {
        let mut av = mat_vec(a, &v);
        nv = norm(&av).max(1e-12);
        for x in av.iter_mut() {
            *x /= nv;
        }
        v = av;
    }
    let av = mat_vec(a, &v);
    let lambda = dot(&v, &av);
    (lambda, v)
}

fn deflate(a: &[Vec<f64>], lambda: f64, v: &[f64]) -> Vec<Vec<f64>> {
    let d = a.len();
    let mut b = a.to_vec();
    for i in 0..d {
        for j in 0..d {
            b[i][j] -= lambda * v[i] * v[j];
        }
    }
    b
}

fn add_pca_coordinates(pairs: &mut [PairFeature], seed: u64) {
    if pairs.is_empty() {
        return;
    }
    let mut x = feature_matrix(pairs);
    normalize_columns(&mut x);
    let c = covariance(&x);
    if c.is_empty() {
        return;
    }
    let (l1, pc1) = power_iteration(&c, seed ^ 0xBADC0FFEE, 80);
    let c2 = deflate(&c, l1, &pc1);
    let (_l2, pc2) = power_iteration(&c2, seed ^ 0xC0FFEE123, 80);

    for (row, pf) in x.iter().zip(pairs.iter_mut()) {
        pf.latent_x = dot(row, &pc1);
        pf.latent_y = dot(row, &pc2);
    }
}

// -----------------------------
// SVG and CSV output
// -----------------------------

fn color_for_class(class_name: &str) -> &'static str {
    match class_name {
        "win" => "#111111",
        "fork" => "#b21f2d",
        "block" => "#1f4f99",
        "pressure" => "#a86f00",
        _ => "#999999",
    }
}

fn heat_color(v: f64, min_v: f64, max_v: f64) -> String {
    let t = if max_v > min_v {
        ((v - min_v) / (max_v - min_v)).clamp(0.0, 1.0)
    } else {
        0.0
    };
    // Monochrome + teal-ish accent, directly encoded for SVG readability.
    let r = (245.0 - 170.0 * t) as i32;
    let g = (245.0 - 60.0 * t) as i32;
    let b = (245.0 - 105.0 * t) as i32;
    format!("#{r:02x}{g:02x}{b:02x}")
}

fn write_board_svg(path: PathBuf, board: &Board, cells: &[Ax], radius: i32) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    let scale = 26.0;
    let pad = 70.0;
    let width = 2.0 * scale * 3.0_f64.sqrt() * radius as f64 + 2.0 * pad + 80.0;
    let height = 3.0 * scale * radius as f64 + 2.0 * pad + 80.0;
    let cx0 = width / 2.0;
    let cy0 = height / 2.0;

    writeln!(f, r#"<svg xmlns="http://www.w3.org/2000/svg" width="{:.0}" height="{:.0}" viewBox="0 0 {:.0} {:.0}">"#, width, height, width, height)?;
    writeln!(f, r#"<rect width="100%" height="100%" fill="#fbfbf8"/>"#)?;
    writeln!(f, r#"<text x="24" y="36" font-family="monospace" font-size="18" fill="#111">Hex Threat Manifold Microscope — board layer</text>"#)?;

    for &p in cells {
        let (x, y) = axial_to_xy(p, scale);
        let cx = cx0 + x;
        let cy = cy0 + y;
        let poly = hex_polygon(cx, cy, scale * 0.94);
        writeln!(f, r#"<polygon points="{}" fill="#ffffff" stroke="#deded8" stroke-width="1"/>"#, poly)?;
        match board.get(p) {
            Stone::Black => {
                writeln!(f, r#"<circle cx="{:.3}" cy="{:.3}" r="{:.3}" fill="#111111"/>"#, cx, cy, scale * 0.42)?;
            }
            Stone::White => {
                writeln!(f, r#"<circle cx="{:.3}" cy="{:.3}" r="{:.3}" fill="#ffffff" stroke="#111111" stroke-width="2"/>"#, cx, cy, scale * 0.42)?;
            }
            Stone::Empty => {}
        }
    }
    writeln!(f, r#"</svg>"#)?;
    Ok(())
}

fn write_heatmap_svg(path: PathBuf, board: &Board, cells: &[Ax], feats: &[CellFeature], radius: i32) -> std::io::Result<()> {
    let fmap: HashMap<Ax, &CellFeature> = feats.iter().map(|cf| (cf.p, cf)).collect();
    let mut f = BufWriter::new(File::create(path)?);
    let scale = 26.0;
    let pad = 70.0;
    let width = 2.0 * scale * 3.0_f64.sqrt() * radius as f64 + 2.0 * pad + 80.0;
    let height = 3.0 * scale * radius as f64 + 2.0 * pad + 80.0;
    let cx0 = width / 2.0;
    let cy0 = height / 2.0;
    let min_v = feats.iter().map(|x| x.candidate_score).fold(f64::INFINITY, f64::min);
    let max_v = feats.iter().map(|x| x.candidate_score).fold(f64::NEG_INFINITY, f64::max);

    writeln!(f, r#"<svg xmlns="http://www.w3.org/2000/svg" width="{:.0}" height="{:.0}" viewBox="0 0 {:.0} {:.0}">"#, width, height, width, height)?;
    writeln!(f, r#"<rect width="100%" height="100%" fill="#fbfbf8"/>"#)?;
    writeln!(f, r#"<text x="24" y="36" font-family="monospace" font-size="18" fill="#111">cell threat scalar field</text>"#)?;
    writeln!(f, r#"<text x="24" y="58" font-family="monospace" font-size="12" fill="#555">darker cells are high own-threat / high block-value candidate cells</text>"#)?;

    for &p in cells {
        let (x, y) = axial_to_xy(p, scale);
        let cx = cx0 + x;
        let cy = cy0 + y;
        let poly = hex_polygon(cx, cy, scale * 0.94);
        let fill = if let Some(cf) = fmap.get(&p) {
            heat_color(cf.candidate_score, min_v, max_v)
        } else {
            "#ffffff".to_string()
        };
        writeln!(f, r#"<polygon points="{}" fill="{}" stroke="#deded8" stroke-width="1"/>"#, poly, fill)?;
        match board.get(p) {
            Stone::Black => {
                writeln!(f, r#"<circle cx="{:.3}" cy="{:.3}" r="{:.3}" fill="#111111"/>"#, cx, cy, scale * 0.39)?;
            }
            Stone::White => {
                writeln!(f, r#"<circle cx="{:.3}" cy="{:.3}" r="{:.3}" fill="#ffffff" stroke="#111111" stroke-width="2"/>"#, cx, cy, scale * 0.39)?;
            }
            Stone::Empty => {}
        }
    }

    writeln!(f, r#"</svg>"#)?;
    Ok(())
}

fn write_latent_svg(path: PathBuf, pairs: &[PairFeature]) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    let width = 960.0;
    let height = 720.0;
    let pad = 72.0;

    let min_x = pairs.iter().map(|p| p.latent_x).fold(f64::INFINITY, f64::min);
    let max_x = pairs.iter().map(|p| p.latent_x).fold(f64::NEG_INFINITY, f64::max);
    let min_y = pairs.iter().map(|p| p.latent_y).fold(f64::INFINITY, f64::min);
    let max_y = pairs.iter().map(|p| p.latent_y).fold(f64::NEG_INFINITY, f64::max);

    let sx = |x: f64| pad + (x - min_x) / (max_x - min_x + 1e-9) * (width - 2.0 * pad);
    let sy = |y: f64| height - pad - (y - min_y) / (max_y - min_y + 1e-9) * (height - 2.0 * pad);

    writeln!(f, r#"<svg xmlns="http://www.w3.org/2000/svg" width="{:.0}" height="{:.0}" viewBox="0 0 {:.0} {:.0}">"#, width, height, width, height)?;
    writeln!(f, r#"<rect width="100%" height="100%" fill="#fbfbf8"/>"#)?;
    writeln!(f, r#"<text x="32" y="38" font-family="monospace" font-size="20" fill="#111">pair-move latent manifold: Sym²(H)</text>"#)?;
    writeln!(f, r#"<text x="32" y="62" font-family="monospace" font-size="12" fill="#555">PCA of pair features: own gain, block gain, synergy, distance, win/block/fork obligations</text>"#)?;

    // Axes.
    writeln!(f, r#"<line x1="{pad}" y1="{}" x2="{}" y2="{}" stroke="#ccc"/>"#, height - pad, width - pad, height - pad)?;
    writeln!(f, r#"<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{}" stroke="#ccc"/>"#, height - pad)?;

    // Draw quiet first, important later.
    let classes = ["quiet", "pressure", "block", "fork", "win"];
    for class_name in classes {
        for p in pairs.iter().filter(|p| p.class_name == class_name) {
            let x = sx(p.latent_x);
            let y = sy(p.latent_y);
            let col = color_for_class(&p.class_name);
            let r = match p.class_name.as_str() {
                "win" => 5.5,
                "fork" => 4.2,
                "block" => 3.5,
                "pressure" => 3.0,
                _ => 2.0,
            };
            let opacity = match p.class_name.as_str() {
                "quiet" => 0.25,
                _ => 0.78,
            };
            writeln!(f, r#"<circle cx="{:.3}" cy="{:.3}" r="{:.2}" fill="{}" fill-opacity="{:.2}"/>"#, x, y, r, col, opacity)?;
        }
    }

    // Legend.
    let mut lx = 34.0;
    let ly = height - 28.0;
    for class_name in classes {
        writeln!(f, r#"<circle cx="{:.1}" cy="{:.1}" r="5" fill="{}"/>"#, lx, ly, color_for_class(class_name))?;
        writeln!(f, r#"<text x="{:.1}" y="{:.1}" font-family="monospace" font-size="12" fill="#333">{}</text>"#, lx + 10.0, ly + 4.0, class_name)?;
        lx += 105.0;
    }

    writeln!(f, r#"</svg>"#)?;
    Ok(())
}

fn write_cells_csv(path: PathBuf, feats: &[CellFeature]) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    writeln!(f, "q,r,own_live_score,opp_live_score,own_immediate_wins,opp_immediate_wins,fork_potential,smooth_field,candidate_score")?;
    for cf in feats {
        writeln!(
            f,
            "{},{},{:.9},{:.9},{},{},{:.9},{:.9},{:.9}",
            cf.p.q, cf.p.r, cf.own_live_score, cf.opp_live_score,
            cf.own_immediate_wins, cf.opp_immediate_wins,
            cf.fork_potential, cf.smooth_field, cf.candidate_score
        )?;
    }
    Ok(())
}

fn write_pairs_csv(path: PathBuf, pairs: &[PairFeature]) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    writeln!(f, "a_q,a_r,b_q,b_r,own_gain,block_gain,synergy,distance,immediate_win,immediate_block,post_obligations,over_two_obligations,latent_x,latent_y,class")?;
    for p in pairs {
        writeln!(
            f,
            "{},{},{},{},{:.9},{:.9},{:.9},{:.9},{},{},{},{},{:.9},{:.9},{}",
            p.a.q, p.a.r, p.b.q, p.b.r,
            p.own_gain, p.block_gain, p.synergy, p.distance,
            p.immediate_win, p.immediate_block,
            p.post_obligations, p.over_two_obligations,
            p.latent_x, p.latent_y, p.class_name
        )?;
    }
    Ok(())
}

fn top_pairs_by_score<'a>(pairs: &'a [PairFeature], n: usize) -> Vec<&'a PairFeature> {
    let mut refs: Vec<&PairFeature> = pairs.iter().collect();
    refs.sort_by(|a, b| {
        let sa = a.own_gain + 1.25 * a.block_gain + 2.0 * a.synergy + 250.0 * a.over_two_obligations as f64 + if a.immediate_win { 10000.0 } else { 0.0 };
        let sb = b.own_gain + 1.25 * b.block_gain + 2.0 * b.synergy + 250.0 * b.over_two_obligations as f64 + if b.immediate_win { 10000.0 } else { 0.0 };
        sb.partial_cmp(&sa).unwrap_or(Ordering::Equal)
    });
    refs.truncate(n);
    refs
}

fn count_classes(pairs: &[PairFeature]) -> HashMap<String, usize> {
    let mut h = HashMap::new();
    for p in pairs {
        *h.entry(p.class_name.clone()).or_insert(0) += 1;
    }
    h
}

fn write_summary(
    path: PathBuf,
    cfg: &Config,
    board: &Board,
    cells: &[Ax],
    candidates: &[CellFeature],
    pairs: &[PairFeature],
) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    let classes = count_classes(pairs);
    let top = top_pairs_by_score(pairs, 12);

    writeln!(f, "# Hex Threat Manifold Microscope")?;
    writeln!(f)?;
    writeln!(f, "## Run")?;
    writeln!(f)?;
    writeln!(f, "- radius: `{}`", cfg.radius)?;
    writeln!(f, "- position: `{}`", cfg.position)?;
    writeln!(f, "- side evaluated: `{}`", cfg.color.name())?;
    writeln!(f, "- observed cells: `{}`", cells.len())?;
    writeln!(f, "- occupied stones: `{}`", board.stones.len())?;
    writeln!(f, "- empty cell candidates retained: `{}`", candidates.len())?;
    writeln!(f, "- pair moves embedded: `{}`", pairs.len())?;
    writeln!(f, "- candidate pruning: top `{}` cells before unordered pair enumeration", cfg.candidates)?;
    writeln!(f)?;
    writeln!(f, "## Class counts")?;
    writeln!(f)?;
    for key in ["win", "fork", "block", "pressure", "quiet"] {
        writeln!(f, "- `{}`: `{}`", key, classes.get(key).copied().unwrap_or(0))?;
    }
    writeln!(f)?;
    writeln!(f, "## Top pair moves")?;
    writeln!(f)?;
    writeln!(f, "| rank | pair | class | own gain | block gain | synergy | obligations |")?;
    writeln!(f, "|---:|---|---:|---:|---:|---:|---:|")?;
    for (i, p) in top.iter().enumerate() {
        writeln!(
            f,
            "| {} | `({}, {}) + ({}, {})` | `{}` | {:.2} | {:.2} | {:.2} | {} |",
            i + 1,
            p.a.q, p.a.r, p.b.q, p.b.r,
            p.class_name, p.own_gain, p.block_gain, p.synergy, p.post_obligations
        )?;
    }
    writeln!(f)?;
    writeln!(f, "## Working conjectures")?;
    writeln!(f)?;
    writeln!(f, "1. **Threat-cone compression.** The strategically live subset of `Sym²(H)` is much lower-dimensional than the legal pair-space. In the SVG, this appears as a compressed tactical cone separated from the quiet reservoir.")?;
    writeln!(f, "2. **Fork curvature.** Pair moves that produce more than two post-move immediate obligations form high-curvature cusps in the latent map, because a two-stone reply cannot cover all branches.")?;
    writeln!(f, "3. **Reservoir analogy.** Most legal pair moves are combinatorially real but dynamically invisible: they barely change win/block/fork observables and therefore occupy a quiet reservoir of the move manifold.")?;
    writeln!(f)?;
    writeln!(f, "## Files")?;
    writeln!(f)?;
    writeln!(f, "- `board.svg`: board layer")?;
    writeln!(f, "- `threat_heatmap.svg`: scalar cell-threat field")?;
    writeln!(f, "- `pair_latent.svg`: PCA latent manifold of pair moves")?;
    writeln!(f, "- `cells.csv`: per-cell features")?;
    writeln!(f, "- `pairs.csv`: per-pair features")?;
    Ok(())
}

// -----------------------------
// Main
// -----------------------------

fn main() -> std::io::Result<()> {
    let cfg = parse_args();
    fs::create_dir_all(&cfg.out)?;

    let board = make_position(&cfg.position, cfg.seed);
    let radius = cfg.radius.max(board.occupied_bounds_radius() + 2);
    let cells = hex_disk(radius);

    let all_features = cell_features(&board, &cells, cfg.color, cfg.kernel_sigma);
    let keep = cfg.candidates.min(all_features.len());
    let candidates = all_features.iter().take(keep).cloned().collect::<Vec<_>>();

    eprintln!("observed cells: {}", cells.len());
    eprintln!("empty cells: {}", all_features.len());
    eprintln!("candidate cells retained: {}", candidates.len());
    eprintln!("pair enumeration upper bound: {}", candidates.len() * candidates.len().saturating_sub(1) / 2);

    let mut pairs = pair_features(&board, &candidates, &cells, cfg.color);
    add_pca_coordinates(&mut pairs, cfg.seed);

    eprintln!("pairs embedded: {}", pairs.len());
    let class_counts = count_classes(&pairs);
    eprintln!("class counts: {:?}", class_counts);

    write_board_svg(cfg.out.join("board.svg"), &board, &cells, radius)?;
    write_heatmap_svg(cfg.out.join("threat_heatmap.svg"), &board, &cells, &all_features, radius)?;
    write_latent_svg(cfg.out.join("pair_latent.svg"), &pairs)?;
    write_cells_csv(cfg.out.join("cells.csv"), &all_features)?;
    write_pairs_csv(cfg.out.join("pairs.csv"), &pairs)?;
    write_summary(cfg.out.join("summary.md"), &cfg, &board, &cells, &candidates, &pairs)?;

    let mut meta = BufWriter::new(File::create(cfg.out.join("metadata.json"))?);
    writeln!(
        meta,
        "{{\n  \"radius\": {},\n  \"position\": \"{}\",\n  \"seed\": {},\n  \"side\": \"{}\",\n  \"observed_cells\": {},\n  \"empty_cells\": {},\n  \"candidate_cells\": {},\n  \"pairs\": {},\n  \"kernel_sigma\": {}\n}}",
        radius, cfg.position, cfg.seed, cfg.color.name(), cells.len(), all_features.len(), candidates.len(), pairs.len(), cfg.kernel_sigma
    )?;

    println!("wrote {}", cfg.out.display());
    Ok(())
}
