from flask import Flask, render_template, request, jsonify
import os
import re
import json
import urllib.request
import urllib.error

app = Flask(__name__)


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

SUPABASE_TABLE = "properties"


def supabase_request(method, endpoint, data=None, params=""):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "لم يتم ضبط SUPABASE_URL و SUPABASE_SERVICE_ROLE_KEY في إعدادات Render."
        )

    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"

    if params:
        url += f"?{params}"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    if method == "POST":
        headers["Prefer"] = "return=representation"

    request_data = None

    if data is not None:
        request_data = json.dumps(data, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=request_data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")

            if not body:
                return []

            return json.loads(body)

    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"Supabase HTTP {error.code}: {error_body}"
        )

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"تعذر الاتصال بقاعدة بيانات Supabase: {error}"
        )


# ============================================================
# الصفحة الرئيسية
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# جلب جميع العقارات
# ============================================================

@app.route("/api/properties", methods=["GET"])
def get_properties():
    try:
        rows = supabase_request(
            "GET",
            SUPABASE_TABLE,
            params=(
                "select="
                "id,"
                "property_type,"
                "listing_type,"
                "governorate,"
                "area_name,"
                "property_area,"
                "price,"
                "price_type,"
                "phone,"
                "location,"
                "basin,"
                "parcel,"
                "bedrooms,"
                "bathrooms,"
                "notes,"
                "date,"
                "created_at"
                "&order=created_at.desc"
            ),
        )

        results = []

        for row in rows:
            results.append({
                "id": row.get("id"),
                "propertyType": row.get("property_type") or "",
                "listingType": row.get("listing_type") or "",
                "governorate": row.get("governorate") or "",
                "areaName": row.get("area_name") or "",
                "propertyArea": row.get("property_area") or "",
                "price": row.get("price") or "",
                "priceType": row.get("price_type") or "",
                "phone": row.get("phone") or "",
                "location": row.get("location") or "",
                "basin": row.get("basin") or "",
                "parcel": row.get("parcel") or "",
                "bedrooms": row.get("bedrooms") or "",
                "bathrooms": row.get("bathrooms") or "",
                "notes": row.get("notes") or "",
                "date": row.get("date") or "",
            })

        return jsonify({
            "status": "success",
            "results": results
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# البحث
# ============================================================

@app.route("/api/ai-search", methods=["POST"])
def ai_search():
    try:
        data = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip()

        governorates = [
            "عمان",
            "إربد",
            "الزرقاء",
            "السلط",
            "مادبا",
            "جرش",
            "عجلون",
            "المفرق",
            "الكرك",
            "الطفيلة",
            "معان",
            "العقبة",
        ]

        detected_gov = ""

        for gov in governorates:
            if gov in query:
                detected_gov = gov
                break

        luwa_match = re.search(
            r"(لواء\s+[أ-يءآإأؤئًٌٍَُِْ\w\s]+)",
            query
        )

        detected_luwa = (
            luwa_match.group(1).strip()
            if luwa_match
            else ""
        )

        basin_match = re.search(
            r"حوض\s*([أ-يءآإأؤئ0-9\w\-]+)",
            query
        )

        detected_basin = (
            basin_match.group(1)
            if basin_match
            else ""
        )

        piece_match = re.search(
            r"قطعة\s*(رقم)?\s*(\d+)",
            query
        )

        detected_piece = (
            piece_match.group(2)
            if piece_match
            else ""
        )

        prop_type = ""

        if "شقة" in query:
            prop_type = "شقة"
        elif "أرض" in query:
            prop_type = "أرض"

        rows = supabase_request(
            "GET",
            SUPABASE_TABLE,
            params=(
                "select="
                "id,"
                "property_type,"
                "listing_type,"
                "governorate,"
                "area_name,"
                "property_area,"
                "price,"
                "price_type,"
                "phone,"
                "location,"
                "basin,"
                "parcel,"
                "bedrooms,"
                "bathrooms,"
                "notes,"
                "date,"
                "created_at"
                "&order=created_at.desc"
            ),
        )

        filtered_rows = []

        for row in rows:
            matches = True

            if detected_gov:
                if str(row.get("governorate") or "").strip() != detected_gov:
                    matches = False

            if detected_luwa:
                # الحقل area_name هو الأقرب لمفهوم المنطقة/اللواء
                area_name = str(row.get("area_name") or "")
                if detected_luwa not in area_name:
                    matches = False

            if detected_basin:
                basin = str(row.get("basin") or "")
                if detected_basin not in basin:
                    matches = False

            if detected_piece:
                parcel = str(row.get("parcel") or "")
                if parcel != detected_piece:
                    matches = False

            if prop_type:
                if str(row.get("property_type") or "") != prop_type:
                    matches = False

            if matches:
                filtered_rows.append(row)

        # إذا لم توجد محددات بحث، نعرض جميع العقارات.
        # وإذا كان البحث محددًا ولم توجد نتائج، تبقى النتائج فارغة.
        results_list = []

        for row in filtered_rows:
            results_list.append({
                "id": row.get("id"),
                "propertyType": row.get("property_type") or "",
                "listingType": row.get("listing_type") or "",
                "governorate": row.get("governorate") or "",
                "areaName": row.get("area_name") or "",
                "propertyArea": row.get("property_area") or "",
                "price": row.get("price") or "",
                "priceType": row.get("price_type") or "",
                "phone": row.get("phone") or "",
                "location": row.get("location") or "",
                "basin": row.get("basin") or "",
                "parcel": row.get("parcel") or "",
                "bedrooms": row.get("bedrooms") or "",
                "bathrooms": row.get("bathrooms") or "",
                "notes": row.get("notes") or "",
                "date": row.get("date") or "",
            })

        analysis_summary = {
            "المحافظة": detected_gov if detected_gov else "الكل",
            "اللواء": detected_luwa if detected_luwa else "الكل",
            "الحوض": detected_basin if detected_basin else "الكل",
            "رقم القطعة": detected_piece if detected_piece else "الكل",
            "نوع العقار": prop_type if prop_type else "شامل",
        }

        return jsonify({
            "status": "success",
            "analysis": analysis_summary,
            "results": results_list,
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# إضافة عقار
# ============================================================

@app.route("/api/add-property", methods=["POST"])
def add_property():
    try:
        data = request.get_json(silent=True) or {}

        property_data = {
            "property_type": data.get("propertyType") or data.get("property_type") or "",
            "listing_type": data.get("listingType") or data.get("listing_type") or "",
            "governorate": data.get("governorate") or "",
            "area_name": data.get("areaName") or data.get("area_name") or "",
            "property_area": data.get("propertyArea") or data.get("property_area") or "",
            "price": data.get("price") or "",
            "price_type": data.get("priceType") or data.get("price_type") or "",
            "phone": data.get("phone") or "",
            "location": data.get("location") or "",
            "basin": data.get("basin") or "",
            "parcel": data.get("parcel") or "",
            "bedrooms": data.get("bedrooms") or "",
            "bathrooms": data.get("bathrooms") or "",
            "notes": data.get("notes") or "",
            "date": data.get("date") or "",
        }

        rows = supabase_request(
            "POST",
            SUPABASE_TABLE,
            data=property_data,
        )

        inserted = rows[0] if rows else {}

        return jsonify({
            "status": "success",
            "message": "تم إضافة العقار بنجاح إلى منصة ضبعة!",
            "property": {
                "id": inserted.get("id"),
                "propertyType": inserted.get("property_type") or property_data["property_type"],
                "listingType": inserted.get("listing_type") or property_data["listing_type"],
                "governorate": inserted.get("governorate") or property_data["governorate"],
                "areaName": inserted.get("area_name") or property_data["area_name"],
                "propertyArea": inserted.get("property_area") or property_data["property_area"],
                "price": inserted.get("price") or property_data["price"],
                "priceType": inserted.get("price_type") or property_data["price_type"],
                "phone": inserted.get("phone") or property_data["phone"],
                "location": inserted.get("location") or property_data["location"],
                "basin": inserted.get("basin") or property_data["basin"],
                "parcel": inserted.get("parcel") or property_data["parcel"],
                "bedrooms": inserted.get("bedrooms") or property_data["bedrooms"],
                "bathrooms": inserted.get("bathrooms") or property_data["bathrooms"],
                "notes": inserted.get("notes") or property_data["notes"],
                "date": inserted.get("date") or property_data["date"],
            },
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


# ============================================================
# حذف عقار
# ============================================================

@app.route("/api/properties/<int:property_id>", methods=["DELETE"])
def delete_property(property_id):
    try:
        supabase_request(
            "DELETE",
            SUPABASE_TABLE,
            params=f"id=eq.{property_id}",
        )

        return jsonify({
            "status": "success",
            "message": "تم حذف الإعلان بنجاح."
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


# ============================================================
# التشغيل المحلي
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )
