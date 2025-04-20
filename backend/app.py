from flask import Flask, request, jsonify # type: ignore
from flask_cors import CORS # type: ignore
from collections import defaultdict
from datetime import datetime

# ai.py'deki yardımcı fonksiyonları import ediyoruz
from ai import (
    normalize,
    get_recipes_by_ingredient,
    filter_recipes_by_strict_ingredient,
    get_recipe_details,
    get_recipe_name,
    is_related_ingredient
)

app = Flask(__name__)
CORS(app)

# Test endpoint (kontrol amaçlı)
@app.route("/test", methods=["GET"])
def test():
    return jsonify({"message": "Flask API çalışıyor!"})

# Arama endpointi - GET yöntemiyle malzeme arama
@app.route("/api/search", methods=["GET"])  # Bu endpointi kullanın
def search_recipes():
    ingredient = request.args.get('ingredient')
    if not ingredient:
        return jsonify({"error": "Ingredient parametresi eksik."}), 400

    # Malzemeyi virgülle ayırarak birden fazla malzeme olabilir
    ingredients_list = [ing.strip().lower() for ing in ingredient.split(",")]

    # Tariflerin birleştirilmiş hali
    all_recipes = []

    for ing in ingredients_list:
        recipes = get_recipes_by_ingredient(ing)
        strict_filtered = filter_recipes_by_strict_ingredient(recipes, ing)
        all_recipes.extend(strict_filtered)

    # Benzersiz tarifleri döndür
    unique_recipes = {recipe["idMeal"]: recipe for recipe in all_recipes}.values()

    return jsonify(list(unique_recipes))

# Tarif öneri endpointi
@app.route("/suggest_recipes", methods=["POST"])
def suggest_recipes():
    data = request.json
    ingredients = data.get("ingredients", [])
    filters = data.get("filters", [])

    user_ingredients = {}
    for item in ingredients:
        name = normalize(item["name"])
        user_ingredients[name] = (
            item["quantity"],
            item["unit"],
            item["expiry"]
        )

    # Malzeme eşleşmeleri
    recipe_matches = defaultdict(set)
    for ingredient in user_ingredients.keys():
        recipes = get_recipes_by_ingredient(ingredient)
        strict_filtered = filter_recipes_by_strict_ingredient(recipes, ingredient)  # 🔍 sadece gerçekten içerenler
        for recipe in strict_filtered:
            recipe_id = recipe["idMeal"]
            recipe_matches[recipe_id].add(ingredient)

    filtered_recipes = {k: v for k, v in recipe_matches.items() if len(v) >= 1}
    if not filtered_recipes:
        return jsonify({"recipes": [], "message": "Uygun tarif bulunamadı."}), 200

    # SKT'ye göre malzemeleri sırala
    sorted_ingredients = sorted(
        user_ingredients.items(),
        key=lambda x: datetime.strptime(x[1][2], "%d-%m-%Y")
    )

    sorted_recipes = []
    used_recipe_ids = set()
    for ing_name, (_, _, expiry_date) in sorted_ingredients:
        expiry_datetime = datetime.strptime(expiry_date, "%d-%m-%Y")
        ingredient_recipes = []
        for recipe_id in filtered_recipes.keys():
            if ing_name in recipe_matches[recipe_id] and recipe_id not in used_recipe_ids:
                _, _, tags = get_recipe_details(recipe_id)
                match_count = len([tag for tag in filters if tag in tags]) if filters else 0
                ingredient_recipes.append((recipe_id, expiry_datetime, match_count))

        # Etiket eşleşmesi ve isme göre sırala
        ingredient_recipes.sort(key=lambda x: (-x[2], get_recipe_name(x[0])))

        for recipe_id, expiry, match_count in ingredient_recipes:
            sorted_recipes.append({
                "id": recipe_id,
                "name": get_recipe_name(recipe_id),
                "match_count": match_count
            })
            used_recipe_ids.add(recipe_id)

    return jsonify({"recipes": sorted_recipes})

if __name__ == "__main__":
    app.run(debug=True)
