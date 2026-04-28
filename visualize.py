import matplotlib.pyplot as plt
import numpy as np # Import nécessaire pour le calcul des tranches
from datetime import datetime

# --- Les fonctions qui n'ont pas changé (conservées pour le fichier complet) ---

def plot_last_modified_by_year(col):
    """Number of games by last modification year on Steam"""
    games = list(col.find({}, {"last_modified": 1, "_id": 0}))
    if not games:
        print("No data for last modified by year chart.")
        return

    years = []
    for g in games:
        ts = g.get("last_modified")
        if ts:
            year = datetime.utcfromtimestamp(ts).year
            years.append(year)

    year_counts = {}
    for y in years:
        year_counts[y] = year_counts.get(y, 0) + 1

    sorted_years = sorted(year_counts.items())
    x = [str(y) for y, _ in sorted_years]
    y = [count for _, count in sorted_years]

    plt.figure(figsize=(12, 5))
    bars = plt.bar(x, y, color="steelblue")
    
    plt.bar_label(bars, padding=3, fontweight='bold')
    
    plt.title("Number of games by last modification year on Steam")
    plt.xlabel("Year")
    plt.ylabel("Number of games")
    plt.xticks(rotation=45)
    plt.margins(y=0.1)
    plt.tight_layout()
    plt.savefig("games_last_modified_by_year.png")
    plt.show()
    print("Chart saved: games_last_modified_by_year.png")


def plot_release_years(col):
    """Number of games by original release year vs last modification year"""
    games = list(col.find(
        {"release_year": {"$exists": True}, "last_modified": {"$exists": True}},
        {"release_year": 1, "last_modified": 1, "_id": 0}
    ))
    if not games:
        print("No release year data found. Make sure enrich_release_dates() has been called.")
        return

    release_counts = {}
    modified_counts = {}

    for g in games:
        ry = g.get("release_year")
        if ry:
            release_counts[ry] = release_counts.get(ry, 0) + 1

        ts = g.get("last_modified")
        if ts:
            my = datetime.utcfromtimestamp(ts).year
            modified_counts[my] = modified_counts.get(my, 0) + 1

    all_years = sorted(set(list(release_counts.keys()) + list(modified_counts.keys())))
    x = list(range(len(all_years)))
    labels = [str(y) for y in all_years]
    release_vals = [release_counts.get(y, 0) for y in all_years]
    modified_vals = [modified_counts.get(y, 0) for y in all_years]

    plt.figure(figsize=(14, 6))
    bars1 = plt.bar([i - 0.2 for i in x], release_vals, width=0.4, label="Original release year", color="steelblue")
    bars2 = plt.bar([i + 0.2 for i in x], modified_vals, width=0.4, label="Last modified on Steam", color="coral")
    
    plt.bar_label(bars1, padding=3, fontsize=8)
    plt.bar_label(bars2, padding=3, fontsize=8)
    
    plt.xticks(x, labels, rotation=45, ha="right")
    plt.title("Games by original release year vs last modification year on Steam")
    plt.xlabel("Year")
    plt.ylabel("Number of games")
    plt.legend()
    plt.margins(y=0.1)
    plt.tight_layout()
    plt.savefig("release_vs_modified_by_year.png")
    plt.show()
    print("Chart saved: release_vs_modified_by_year.png")


def plot_top_discounts(col, top_n=10):
    """Top games with the biggest discount vs regular price"""
    games = list(col.find(
        {"current_price": {"$exists": True, "$ne": []}},
        {"name": 1, "current_price": 1, "_id": 0}
    ))

    if not games:
        print("No discount data found.")
        return

    discounts = []
    for g in games:
        for deal in g.get("current_price", []):
            price = deal.get("price_usd")
            regular = deal.get("regular_price", {})
            regular_amount = regular.get("amount") if isinstance(regular, dict) else None
            if price is None or regular_amount is None or regular_amount == 0:
                continue
            reduction_pct = ((regular_amount - price) / regular_amount) * 100
            if reduction_pct > 0:
                discounts.append({
                    "name": g["name"][:30],
                    "reduction_pct": round(reduction_pct, 1),
                })
                break

    if not discounts:
        print("No discounts found.")
        return

    top = sorted(discounts, key=lambda x: x["reduction_pct"], reverse=True)[:top_n]
    names = [d["name"] for d in top]
    reductions = [d["reduction_pct"] for d in top]

    plt.figure(figsize=(12, 5))
    bars = plt.barh(names, reductions, color="coral")
    plt.bar_label(bars, labels=[f"{r}%" for r in reductions], padding=4)
    plt.title(f"Top {top_n} games with the biggest discount")
    plt.xlabel("Discount (%)")
    plt.xlim(0, 120)
    plt.tight_layout()
    plt.savefig("top_discounts.png")
    plt.show()
    print("Chart saved: top_discounts.png")


def plot_historical_low_vs_current(col, top_n=10):
    """Compare current price vs historical lowest price (Lollipop Chart)"""
    games = list(col.find(
        {"historical_low": {"$exists": True}, "current_price": {"$exists": True, "$ne": []}},
        {"name": 1, "historical_low": 1, "current_price": 1, "_id": 0}
    ))

    if not games:
        print("No data for historical low comparison.")
        return

    results = []
    for g in games:
        hist = g.get("historical_low", {})
        hist_amount = hist.get("price_usd") if hist else None
        current_amounts = [d["price_usd"] for d in g.get("current_price", []) if d.get("price_usd") is not None]
        if hist_amount is None or not current_amounts:
            continue
        results.append({
            "name": g["name"][:25],
            "current": min(current_amounts),
            "hist_low": hist_amount,
        })

    if not results:
        print("No valid data for historical comparison.")
        return

    results = results[:top_n]
    results = sorted(results, key=lambda x: x["current"])
    
    names = [r["name"] for r in results]
    currents = [r["current"] for r in results]
    hist_lows = [r["hist_low"] for r in results]
    y_pos = range(len(names))

    plt.figure(figsize=(12, 7))
    plt.hlines(y=y_pos, xmin=hist_lows, xmax=currents, color='gray', alpha=0.5, linewidth=3, zorder=1)
    plt.scatter(hist_lows, y_pos, color='coral', s=100, label='Historical Low', zorder=2)
    plt.scatter(currents, y_pos, color='steelblue', s=100, label='Current Price', zorder=2)
    
    for i in range(len(results)):
        gap = currents[i] - hist_lows[i]
        if gap > 0.01 and currents[i] > 0:
            pct_to_low = (gap / currents[i]) * 100
            mid_x = (currents[i] + hist_lows[i]) / 2
            plt.text(mid_x, y_pos[i] + 0.15, f"-{pct_to_low:.0f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
        elif gap <= 0.01:
            plt.text(currents[i] + 0.5, y_pos[i], "At Hist. Low!", va='center', fontsize=9, color='green', fontweight='bold')

    plt.yticks(y_pos, names)
    plt.title("Current Price vs Historical Lowest Price")
    plt.xlabel("Price (USD)")
    plt.legend()
    plt.margins(y=0.1)
    plt.tight_layout()
    plt.savefig("hist_low_vs_current.png")
    plt.show()
    print("Chart saved: hist_low_vs_current.png")

# --- LA FONCTION MODIFIÉE ---

def plot_current_price_distribution(col):
    """Distribution of current prices (Custom Histogram with Labels)"""
    games = list(col.find(
        {"current_price": {"$exists": True, "$ne": []}},
        {"current_price": 1, "_id": 0}
    ))

    if not games:
        print("No current price data found.")
        return

    prices = []
    for g in games:
        deals = g.get("current_price", [])
        amounts = [d["price_usd"] for d in deals if d.get("price_usd") is not None]
        if amounts:
            # On prend le prix le plus bas actuellement disponible
            prices.append(min(amounts))

    if not prices:
        print("No valid prices found.")
        return

    prices = np.array(prices)
    # Pour éviter que les jeux hyper chers n'écrasent le graphique, 
    # on filtre ceux au-dessus de 100$ (on les traitera comme une catégorie "100$+")
    max_plot_price = 100
    filtered_prices = prices[prices <= max_plot_price]
    over_100_count = np.sum(prices > max_plot_price)

    # Définition des tranches de prix personnalisées (bins)
    # 0-5, 5-10, 10-15, ..., 95-100
    bins = list(range(0, max_plot_price + 5, 5)) 

    plt.figure(figsize=(14, 7))
    
    # Dessiner l'histogramme
    # `rwidth=0.9` ajoute un petit espace entre les barres pour la lisibilité
    n, bins_edges, patches = plt.hist(filtered_prices, bins=bins, 
                                     color="steelblue", edgecolor="black", 
                                     alpha=0.8, rwidth=0.9, label='Games under 100$')
    
    # Ajouter les labels de comptage au-dessus de chaque barre
    for i in range(len(n)):
        if n[i] > 0: # N'affiche le chiffre que s'il y a des jeux
            # Place le texte au centre de la tranche (x) et juste au-dessus de la barre (y)
            plt.text(bins_edges[i] + 2.5, n[i] + (max(n)*0.01), int(n[i]), 
                     ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Ajouter une barre spéciale pour les jeux à plus de 100$
    if over_100_count > 0:
        x_over = max_plot_price + 7.5
        plt.bar(x_over, over_100_count, width=4, color="coral", edgecolor="black", label='Games 100$+')
        plt.text(x_over, over_100_count + (max(n)*0.01), int(over_100_count), 
                 ha='center', va='bottom', fontsize=9, fontweight='bold', color='coral')
        
        # Ajuster les ticks de l'axe X pour inclure la catégorie 100$+
        current_ticks = list(range(0, max_plot_price + 10, 10))
        plt.xticks(current_ticks + [x_over], 
                   [str(t) for t in current_ticks] + ['>100$'])
    else:
        plt.xticks(range(0, max_plot_price + 10, 10))

    plt.title("Distribution of current game prices")
    plt.xlabel("Price Range (USD)")
    plt.ylabel("Number of games")
    plt.legend()
    plt.grid(axis='y', alpha=0.3) # Ajoute une grille horizontale légère
    plt.margins(y=0.1) # Espace en haut pour les labels
    plt.tight_layout()
    plt.savefig("price_distribution.png")
    plt.show()
    print("Chart saved: price_distribution.png")