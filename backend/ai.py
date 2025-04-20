import requests # type: ignore
import re
from fractions import Fraction
from collections import defaultdict
from datetime import datetime

# Malzeme isimlerini normalleştirme ve tekil forma indirgeme
def normalize(ingredient):
    ingredient = ingredient.strip().lower()
    if ingredient.endswith("s"):
        ingredient = ingredient[:-1]
    return ingredient


# Miktar ve birimi ayırma fonksiyonu
def parse_measure(measure):
    measure = measure.strip().lower()
    fraction_match = re.match(r"(\d+/\d+)\s*(.*)", measure)
    if fraction_match:
        quantity_str, unit = fraction_match.groups()
        return quantity_str, unit if unit else ""
    match = re.match(r"(\d+)\s*(.*)", measure)
    if match:
        quantity, unit = match.groups()
        return quantity, unit if unit else ""
    return "0", ""

# Malzemeler arasında eşleşme kontrolü
def is_related_ingredient(user_ing, recipe_ing):
    user_ing = normalize(user_ing)
    recipe_ing = normalize(recipe_ing)
    return user_ing in recipe_ing or recipe_ing in user_ing

# TheMealDB API'den malzeme ile tarif alma
def get_recipes_by_ingredient(ingredient):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"'{ingredient}' için API isteği başarısız: {response.status_code}")
        return []
    data = response.json()
    meals = data.get("meals")
    return meals if meals is not None else []

# get_recipes_by_ingredient içinden gelen tarifleri detaylı kontrol et
def filter_recipes_by_strict_ingredient(recipes, target_ingredient):
    filtered = []
    for recipe in recipes:
        recipe_id = recipe["idMeal"]
        ingredients, _, _ = get_recipe_details(recipe_id)
        for ing in ingredients:
            if is_related_ingredient(ing, target_ingredient):
                filtered.append(recipe)
                break
    return filtered


# Tarifin detaylarını alma (malzemeler, açıklama, etiketler)
def get_recipe_details(recipe_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(url)
    data = response.json()
    if data.get("meals"):
        meal = data["meals"][0]
        ingredients = {}
        for i in range(1, 21):
            ing = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ing and measure:
                quantity, unit = parse_measure(measure)
                ingredients[normalize(ing)] = (quantity, unit)
        instructions = meal.get("strInstructions", "Açıklama bulunamadı.")
        tags = meal.get("strTags", "").split(",") if meal.get("strTags") else []
        tags = [tag.strip().lower() for tag in tags]
        return ingredients, instructions, tags
    return {}, "Açıklama bulunamadı.", []

# Tarif adını alma
def get_recipe_name(recipe_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(url)
    data = response.json()
    if data.get("meals"):
        return data["meals"][0]["strMeal"]
    return "Bilinmeyen Tarif"

# Tüm etiketleri toplama
def get_all_tags():
    tags = set()
    url = "https://www.themealdb.com/api/json/v1/1/list.php?c=list"
    response = requests.get(url)
    if response.status_code != 200:
        print("Kategoriler alınamadı. Lütfen internet bağlantınızı kontrol edin.")
        return tags
    
    data = response.json()
    categories = data.get("meals", [])
    if not categories:
        print("Hiç kategori bulunamadı.")
        return tags
    
    for category in categories:
        category_name = category["strCategory"]
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={category_name}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"'{category_name}' kategorisi için tarifler alınamadı.")
            continue
        
        data = response.json()
        meals = data.get("meals", [])
        if not meals:
            continue
        
        for meal in meals:
            recipe_id = meal["idMeal"]
            url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("meals"):
                    meal_data = data["meals"][0]
                    if meal_data.get("strTags"):
                        meal_tags = meal_data["strTags"].split(",")
                        tags.update([tag.strip().lower() for tag in meal_tags])
    
    return sorted(list(tags))

# Ana fonksiyon
def main():
    # Tüm etiketleri al
    print("Etiketler yükleniyor...")
    all_tags = get_all_tags()
    if not all_tags:
        print("Etiketler alınamadı. Lütfen internet bağlantınızı kontrol edin.")
        return
    print("Mevcut etiketler:", ", ".join(all_tags))

    # Kullanıcıdan etiket seçimi (birden fazla etiket virgülle ayrılmış veya close)
    selected_tags = []
    while True:
        selected_tags_input = input("Lütfen etiketleri virgülle ayırarak girin (örneğin, Dessert, Vegetarian) ya da atlamak için 'close' yazın: ").strip().lower()
        if selected_tags_input == "close":
            break
        if selected_tags_input:
            selected_tags = [tag.strip() for tag in selected_tags_input.split(",")]
            invalid_tags = [tag for tag in selected_tags if tag not in all_tags]
            if invalid_tags:
                print(f"Geçersiz etiketler: {', '.join(invalid_tags)}. Lütfen listeden etiketler seçin.")
            else:
                break

    # Kullanıcıdan malzemeleri alma
    user_ingredients = {}
    print("\nMalzemeleri 'miktar malzeme, GÜN-AY-YIL' formatında girin (örneğin, '1 onion, 10-03-2025'). Bitirmek için 'close' yazın.")
    while True:
        ingredient_input = input("Malzeme girin: ").strip().lower()
        if ingredient_input == "close":
            break
        match = re.match(r"(\d+/\d+|\d+)\s*(\w*)\s+([^,]+),\s*(\d{2}-\d{2}-\d{4})", ingredient_input)
        if match:
            quantity, unit, name, expiry_date = match.groups()
            try:
                datetime.strptime(expiry_date, "%d-%m-%Y")
            except ValueError:
                print("Geçersiz tarih formatı! Lütfen GÜN-AY-YIL (örneğin, 10-03-2025) formatında girin.")
                continue
            normalized_name = normalize(name.strip())
            user_ingredients[normalized_name] = (quantity, unit if unit else "", expiry_date)
        else:
            print("Geçersiz giriş! Lütfen 'miktar malzeme, GÜN-AY-YIL' formatında girin (örneğin, '1 onion, 10-03-2025').")

    if not user_ingredients:
        print("Hiç malzeme girilmedi!")
        return

    # Girilen malzemeler için tarif arama
    recipe_matches = defaultdict(set)
    for ingredient in user_ingredients.keys():
        recipes = get_recipes_by_ingredient(ingredient)
        for recipe in recipes:
            recipe_id = recipe["idMeal"]
            recipe_matches[recipe_id].add(ingredient)

    # En az 2 malzeme ile eşleşen tarifleri filtreleme
    min_matches = 2
    filtered_recipes = {k: v for k, v in recipe_matches.items() if len(v) >= min_matches}

    if not filtered_recipes:
        print("Girilen malzemelerle en az 2 malzeme içeren tarif bulunamadı.")
        return

    # Malzemeleri SKT'ye göre sıralama
    sorted_ingredients = sorted(
        user_ingredients.items(),
        key=lambda x: datetime.strptime(x[1][2], "%d-%m-%Y")
    )

    # Tarifleri SKT gruplarına göre sıralama
    sorted_recipes = []
    used_recipe_ids = set()  # Tekrarları önlemek için
    for ing_name, (_, _, expiry_date) in sorted_ingredients:
        expiry_datetime = datetime.strptime(expiry_date, "%d-%m-%Y")
        # Bu malzemeyi içeren tarifleri al
        ingredient_recipes = []
        for recipe_id in filtered_recipes.keys():
            if ing_name in recipe_matches[recipe_id] and recipe_id not in used_recipe_ids:
                # Etiket eşleşmesini hesapla
                _, _, tags = get_recipe_details(recipe_id)
                match_count = len([tag for tag in selected_tags if tag in tags]) if selected_tags else 0
                ingredient_recipes.append((recipe_id, expiry_datetime, match_count))
        
        # Etiket eşleşmesine ve tarif adına göre sırala
        ingredient_recipes.sort(key=lambda x: (-x[2], get_recipe_name(x[0])))
        
        # Tarifleri ekle ve kullanılanları işaretle
        for recipe_id, expiry, match_count in ingredient_recipes:
            sorted_recipes.append((recipe_id, expiry, match_count))
            used_recipe_ids.add(recipe_id)

    if not sorted_recipes:
        print("Uygun tarif bulunamadı.")
        return

    # Tarifleri listeleme
    print("\nBulunan tarifler:")
    for idx, (recipe_id, _, _) in enumerate(sorted_recipes, start=1):
        print(f"{idx}. {get_recipe_name(recipe_id)}")

    # Kullanıcıdan tarif seçimi
    try:
        selection = int(input("\nSeçmek istediğiniz tarifin numarasını girin: "))
        if selection < 1 or selection > len(sorted_recipes):
            print("Geçersiz numara!")
            return
    except ValueError:
        print("Lütfen geçerli bir numara girin!")
        return

    selected_recipe_id = sorted_recipes[selection - 1][0]

    # Tarifin detaylarını alma
    recipe_ingredients, instructions, _ = get_recipe_details(selected_recipe_id)

    # Eksik malzemeleri hesaplama
    missing_ingredients = []
    for ing, (req_quantity, req_unit) in recipe_ingredients.items():
        matching_ingredients = [user_ing for user_ing in user_ingredients.keys() if is_related_ingredient(user_ing, ing)]
        if matching_ingredients:
            user_ing = matching_ingredients[0]
            user_quantity, user_unit, expiry_date = user_ingredients[user_ing]
            req_qty_num = float(Fraction(req_quantity))
            user_qty_num = float(Fraction(user_quantity))
            if user_qty_num < req_qty_num:
                if user_unit == req_unit:
                    missing_qty = req_qty_num - user_qty_num
                    missing_ingredients.append(f"{missing_qty} {req_unit} {ing} (You have: {user_quantity} {user_unit})")
                else:
                    missing_ingredients.append(f"{req_quantity} {req_unit} {ing} (You have: {user_quantity} {user_unit} {user_ing})")
        else:
            missing_ingredients.append(f"{req_quantity} {req_unit} {ing}")

    # Sonuçları yazdırma
    print(f"\nSeçilen tarif: {get_recipe_name(selected_recipe_id)}\n")
    print("Tarif açıklaması:")
    print(instructions)
    print("\nEksik malzemeler:")
    if not missing_ingredients:
        print("Tüm malzemelere sahipsiniz. Tarifi yapabilirsiniz!")
    else:
        print(", \n".join(missing_ingredients))
    
    print("\n\n")
# Kodu çalıştırma
# if __name__ == "__main__":
#     main()