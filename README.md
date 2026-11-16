# RoofLamp 屋頂燈罩生成器

微縮場景屋頂燈罩的參數化生成器（瀏覽器），支援 FDM／光固化／雷射切割。

- 屋頂：平頂、單斜、雙斜、四面斜；窗／門（可多層）、燈孔（圓／方／六邊形、網格／蜂巢）
- 輸出：STEP（精確 CAD）、STL、雷射平面拆解圖（DXF／SVG）、表面試板（磚／木／日式／美式）

## 線上版（GitHub Pages）
純前端，可在任何電腦開啟：STL、DXF、SVG、試板 STL 都可用。
**STEP 需要本機後端，線上版不支援。**

## 本機完整版（含 STEP）
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
python3 server.py 8090      # 開啟 http://localhost:8090
```
macOS 也可雙擊 `啟動 RoofLamp.command`。

## 授權
第三方：three.js、three-bvh-csg、three-mesh-bvh（皆 MIT），放在 `vendor/`。
