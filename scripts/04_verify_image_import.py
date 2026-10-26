# -*- coding: utf-8 -*-
"""Smoke-test custom image conversion without publishing an image asset."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from importlib.util import module_from_spec, spec_from_file_location


script = Path(__file__).with_name("04_add_image_questions.py")
spec = spec_from_file_location("image_import", script)
module = module_from_spec(spec)
spec.loader.exec_module(module)

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    image = Image.new("RGB", (360, 440), "#244666")
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 55, 290, 330), fill="#f2a364")
    draw.ellipse((115, 135, 155, 175), fill="#182133")
    draw.ellipse((205, 135, 245, 175), fill="#182133")
    image.save(root / "portrait.png")
    manifest = root / "questions.json"
    manifest.write_text(json.dumps({"questions": [{
        "id": "test_portrait_01",
        "category": "초상화",
        "title": "테스트 인물",
        "answers": ["테스트 인물"],
        "hint1": "테스트 힌트",
        "hint2": "초성 힌트: ㅌ ㅅ ㅌ",
        "image": "portrait.png",
    }]}), encoding="utf-8")
    questions, paintings = module.build(manifest)
    question, painting = questions[0], paintings["test_portrait_01"]
    assert question["category"] == "초상화"
    assert len(question["polygons"]) == 260
    assert (question["width"], question["height"]) == (180, 220)
    assert painting["strokes"] and painting["strokes"][0][2] >= painting["strokes"][-1][2]
    print(f"OK: {len(question['polygons'])} triangles, {len(painting['strokes'])} brush strokes")
