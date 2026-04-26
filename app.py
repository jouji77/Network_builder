from flask import Flask, render_template, request, jsonify, send_file
from modules.network_designer import calculate_network_design, generate_floor_plan_svg
from modules.excel_exporter import build_excel
from datetime import date

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/design", methods=["POST"])
def design():
    data = request.get_json(force=True)
    try:
        width = float(data.get("width", 360))
        height = float(data.get("height", 152))
        requirements = {
            "ssid": data.get("ssid", "FACTORY-WIFI"),
            "ap_spacing": float(data.get("ap_spacing", 50)),
            "coverage_radius": float(data.get("coverage_radius", 30)),
        }
        result = calculate_network_design(width, height, requirements)
        result["floor_plan_svg"] = generate_floor_plan_svg(result)
        return jsonify({"success": True, "design": result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route("/api/export/excel", methods=["POST"])
def export_excel():
    data = request.get_json(force=True)
    try:
        width = float(data.get("width", 360))
        height = float(data.get("height", 152))
        requirements = {
            "ssid": data.get("ssid", "FACTORY-WIFI"),
            "ap_spacing": float(data.get("ap_spacing", 50)),
            "coverage_radius": float(data.get("coverage_radius", 30)),
        }
        design_result = calculate_network_design(width, height, requirements)
        buf = build_excel(design_result)
        filename = f"network_design_{date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
