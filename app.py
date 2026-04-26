from flask import Flask, render_template, request, jsonify
from modules.network_designer import calculate_network_design, generate_floor_plan_svg

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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
