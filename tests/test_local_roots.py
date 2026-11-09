from pathlib import Path

from nexplorer.local_roots import local_roots


def test_windows_offers_the_drive_letters():
    roots = local_roots("win32", drives=lambda: ["C:\\", "D:\\"])
    assert roots == [("C:", "C:\\"), ("D:", "D:\\")]


def test_linux_offers_home_slash_and_the_mount_points_of_media_folders(tmp_path):
    media, mnt, run = tmp_path / "media", tmp_path / "mnt", tmp_path / "run"
    for d in (media / "stick", media / "plain-folder", mnt / "disk", run / "card"):
        d.mkdir(parents=True)
    (media / "a-file").write_text("x")
    mounted = {str(media / "stick"), str(mnt / "disk"), str(run / "card"), str(media / "a-file")}
    roots = local_roots(
        "linux",
        home=tmp_path / "home",
        media_parents=[str(media), str(mnt), str(run), str(tmp_path / "missing")],
        is_mount=lambda p: p in mounted,
    )
    assert roots == [
        ("Home", str(tmp_path / "home")),
        ("/", "/"),
        (str(media / "stick"), str(media / "stick")),
        (str(mnt / "disk"), str(mnt / "disk")),
        (str(run / "card"), str(run / "card")),
    ]


def test_linux_reads_the_mounts_again_on_each_call(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    kwargs = dict(home=Path("/h"), media_parents=[str(media)], is_mount=lambda p: True)
    assert len(local_roots("linux", **kwargs)) == 2
    (media / "sd").mkdir()
    assert len(local_roots("linux", **kwargs)) == 3
