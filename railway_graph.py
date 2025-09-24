import math
import networkx as nx
import matplotlib.pyplot as plt

# --- Station coordinates (simplified major network) ---
nodes = {
    "Helsinki": (60.1699, 24.9384),
    "Pasila": (60.1983, 24.9333),
    "Espoo": (60.2055, 24.6559),
    "Kirkkonummi": (60.1235, 24.4380),
    "Karjaa": (60.0717, 23.6547),
    "Salo": (60.3845, 23.1280),
    "Turku": (60.4518, 22.2666),
    "Hanko": (59.8245, 22.9707),
    "Riihimäki": (60.7372, 24.7805),
    "Hämeenlinna": (60.9959, 24.4643),
    "Toijala": (61.1700, 23.8650),
    "Tampere": (61.4978, 23.7610),
    "Jämsä": (61.8647, 25.1900),
    "Jyväskylä": (62.2415, 25.7209),
    "Seinäjoki": (62.7903, 22.8406),
    "Vaasa": (63.0951, 21.6158),
    "Kokkola": (63.8385, 23.1306),
    "Oulu": (65.0121, 25.4651),
    "Kemi": (65.7369, 24.5637),
    "Tornio": (65.8481, 24.1466),
    "Rovaniemi": (66.5039, 25.7294),
    "Kemijärvi": (66.7131, 27.4306),
    "Lahti": (60.9827, 25.6615),
    "Kouvola": (60.8670, 26.7042),
    "Kotka Harbour": (60.4630, 26.9458),
    "Lappeenranta": (61.0583, 28.1887),
    "Imatra": (61.1719, 28.7726),
    "Parikkala": (61.5448, 29.5030),
    "Joensuu": (62.6010, 29.7636),
    "Mikkeli": (61.6886, 27.2736),
    "Pieksämäki": (62.3000, 27.1333),
    "Kuopio": (62.8924, 27.6783),
    "Iisalmi": (63.5610, 27.1882),
    "Kajaani": (64.2273, 27.7284),
    "Kontiomäki": (64.7667, 27.6000),
    "Pori": (61.4850, 21.7970),
    "Kokemäki": (61.2562, 22.3557),
}

# --- Direct edges only ---
edges = [
    ("Helsinki","Pasila"),("Pasila","Espoo"),("Espoo","Kirkkonummi"),
    ("Kirkkonummi","Karjaa"),("Karjaa","Salo"),("Salo","Turku"),
    ("Karjaa","Hanko"),
    ("Pasila","Riihimäki"),("Riihimäki","Hämeenlinna"),
    ("Hämeenlinna","Toijala"),("Toijala","Tampere"),("Toijala","Turku"),
    ("Tampere","Seinäjoki"),("Seinäjoki","Vaasa"),
    ("Seinäjoki","Kokkola"),("Kokkola","Oulu"),("Oulu","Kemi"),
    ("Kemi","Tornio"),
    ("Oulu","Kajaani"),("Kajaani","Kontiomäki"),("Kontiomäki","Iisalmi"),
    ("Iisalmi","Kuopio"),("Kuopio","Pieksämäki"),("Pieksämäki","Mikkeli"),
    ("Mikkeli","Kouvola"),
    ("Oulu","Rovaniemi"),("Rovaniemi","Kemijärvi"),
    ("Helsinki","Lahti"),("Lahti","Kouvola"),
    ("Kouvola","Kotka Harbour"),("Kouvola","Lappeenranta"),
    ("Lappeenranta","Imatra"),("Imatra","Parikkala"),("Parikkala","Joensuu"),
    ("Tampere","Jämsä"),("Jämsä","Jyväskylä"),("Jyväskylä","Pieksämäki"),
    ("Tampere","Kokemäki"),("Kokemäki","Pori"),
]

# --- Haversine distance calculator ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# --- Build graph with direct edges ---
G = nx.Graph()
for u, v in edges:
    lat1, lon1 = nodes[u]
    lat2, lon2 = nodes[v]
    d = haversine(lat1, lon1, lat2, lon2)
    G.add_edge(u, v, weight=d)

# --- Draw using geographic coordinates (lon=x, lat=y) ---
pos = {s: (nodes[s][1], nodes[s][0]) for s in nodes}

plt.figure(figsize=(8, 12))
nx.draw_networkx_nodes(G, pos, node_size=300, node_color="lightblue")
nx.draw_networkx_edges(G, pos, width=1, edge_color="gray")
nx.draw_networkx_labels(G, pos, font_size=7)

edge_labels = {e: f"{d['weight']:.0f} km" for e, d in G.edges.items()}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

plt.title("Finnish Railway Network – Direct Tracks Only")
plt.xlabel("Longitude (°E)")
plt.ylabel("Latitude (°N)")
plt.tight_layout()
plt.show()
