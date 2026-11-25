"""icon.html (the /icon page) shows only icons that ship in pwa/ and the manifest lists; run: python3 test_icon_page.py"""
import json, pathlib, re
HERE = pathlib.Path(__file__).parent / "pwa"


def test_every_image_exists():
    html = (HERE / "icon.html").read_text()
    srcs = set(re.findall(r'src="(/[^"]+)"', html))
    assert srcs
    for s in srcs:
        assert (HERE / s.lstrip("/")).exists(), s


def test_manifest_icons_exist_and_page_says_horus():
    man = json.loads((HERE / "manifest.webmanifest").read_text())
    for i in man["icons"]:
        assert (HERE / i["src"].split("?")[0].lstrip("/")).exists(), i["src"]
    html = (HERE / "icon.html").read_text()
    assert "Horus" in html
    assert "Tyler" not in html and "Youk" not in html


if __name__ == "__main__":
    test_every_image_exists(); test_manifest_icons_exist_and_page_says_horus(); print("ok")
