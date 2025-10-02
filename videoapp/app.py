from flask import Flask, render_template, request, send_file
import os
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("video")
        repeats = int(request.form.get("repeats", 3))  # 重ねる回数
        delay = float(request.form.get("delay", 1.0))  # 遅延秒数

        if not file:
            return "ファイルが選択されていません"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        output_path = os.path.join(OUTPUT_FOLDER, "output.mp4")
        file.save(input_path)

        # 動画長さ取得
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path
        ]
        duration = float(subprocess.check_output(cmd).decode().strip())

        # 総再生時間（最後に全て揃う時間）
        total_time = duration + (repeats - 1) * delay

        filter_parts = []
        overlay_inputs = []
        audio_inputs = []

        # 縮尺設定
        max_scale = 1.0
        min_scale = 0.3  # 最小縮尺

        for i in range(repeats):
            start_delay = i * delay
            # 正確に最後で揃う速度
            speed = duration / (total_time - start_delay)

            # 自動縮尺
            if repeats > 1:
                scale_factor = max_scale - (max_scale - min_scale) * i / (repeats - 1)
            else:
                scale_factor = 1.0

            # 映像: スケール + 遅延 + 倍速
            filter_parts.append(
                f"[0:v]scale=iw*{scale_factor}:ih*{scale_factor},"
                f"setpts=PTS-STARTPTS+{start_delay}/TB,setpts=PTS/{speed}[v{i}]"
            )

            # オーバーレイ
            if i == 0:
                overlay_inputs.append(f"[v0]setpts=PTS-STARTPTS[base]")
            else:
                overlay_inputs.append(f"[base][v{i}]overlay=(W-w)/2:(H-h)/2[base]")

            # 音声: 遅延 + 倍速
            filter_parts.append(
                f"[0:a]adelay={int(start_delay*1000)}|{int(start_delay*1000)},atempo={speed}[a{i}]"
            )
            audio_inputs.append(f"[a{i}]")

        video_filter = "; ".join(filter_parts + overlay_inputs)
        audio_filter = f"{''.join(audio_inputs)}amix=inputs={repeats}[aout]"
        full_filter = f"{video_filter}; {audio_filter}"

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", full_filter,
            "-map", "[base]", "-map", "[aout]",
            "-c:v", "libx264", "-c:a", "aac",
            output_path
        ]

        subprocess.run(cmd, check=True)
        return send_file(output_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
