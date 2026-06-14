from pathlib import Path

from examples.game_viewer import (
    build_corpus_command,
    classify_game_wlu,
    filter_games_by_wlu,
    find_winning_line,
    flatten_corpus_games,
    frames_from_game,
    render_frame_image,
    save_gif,
    sort_games_by_wlu,
)


def test_frames_from_game_replays_moves_incrementally():
    game = {
        "game_id": "demo",
        "moves": [
            {"color": "black", "stones": [[0, 0]]},
            {"color": "white", "stones": [[1, 0], [0, 1]]},
            {"color": "black", "stones": [[-1, 0], [0, -1]]},
        ],
    }

    frames = frames_from_game(game)

    assert len(frames) == 4
    assert frames[1]["black"] == {(0, 0)}
    assert frames[1]["last"] == {(0, 0)}
    assert frames[2]["white"] == {(1, 0), (0, 1)}
    assert frames[3]["black"] == {(0, 0), (-1, 0), (0, -1)}


def test_flatten_corpus_games_accepts_opening_tablebase_shape():
    corpus = {
        "openings": [
            {
                "opening_id": "O0001",
                "white_pair": [[-1, 0], [-1, 1]],
                "best_black_reply": [[0, -1], [-1, -1]],
                "principal_variation": [
                    {"player": "black", "move": [[0, -1], [-1, -1]]},
                    {"player": "white", "move": [[1, 0], [0, 1]]},
                ],
            }
        ]
    }

    games = flatten_corpus_games(corpus)

    assert games[0]["game_id"] == "O0001"
    assert len(games[0]["moves"]) >= 3


def test_render_frame_and_save_gif(tmp_path: Path):
    game = {
        "game_id": "demo",
        "moves": [
            {"color": "black", "stones": [[0, 0]]},
            {"color": "white", "stones": [[1, 0], [0, 1]]},
        ],
    }
    frames = frames_from_game(game)
    image = render_frame_image(frames[-1], size=160)
    path = tmp_path / "demo.gif"

    save_gif(frames, path, size=160, duration_ms=80)

    assert image.size == (160, 160)
    assert path.exists()
    assert path.stat().st_size > 0


def test_classify_and_sort_games_by_wlu():
    games = [
        {"game_id": "u", "moves": []},
        {"game_id": "b", "moves": [{"color": "black", "stones": [[i, 0] for i in range(6)]}]},
        {"game_id": "w", "moves": [{"color": "white", "stones": [[0, i] for i in range(6)]}]},
        {"game_id": "edge", "class": "black_bulk_edge", "moves": []},
    ]

    assert classify_game_wlu(games[0]) == "U"
    assert classify_game_wlu(games[1]) == "B"
    assert classify_game_wlu(games[2]) == "W"
    assert classify_game_wlu(games[3]) == "U"
    assert [game["game_id"] for game in sort_games_by_wlu(games)] == ["b", "w", "edge", "u"]
    assert [game["game_id"] for game in filter_games_by_wlu(games, "W")] == ["w"]


def test_find_winning_line_returns_cells_in_order():
    stones = {(i, 0) for i in range(6)} | {(0, 2)}

    line = find_winning_line(stones)

    assert line == tuple((i, 0) for i in range(6))


def test_build_corpus_command_points_at_corpus_script():
    command = build_corpus_command(radius=3, depth=2, candidate_cells=8, limit=5, out_dir="out_dir")

    assert command[0]
    assert command[1].endswith("opening_tablebase_corpus.py")
    assert "--radius" in command
    assert "3" in command
    assert "--limit" in command
