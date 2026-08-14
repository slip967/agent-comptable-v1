import json

with open('base_produits_vtc_v1.json', encoding='utf-8-sig') as f:
    data = json.load(f)

TO_DELETE = {
    'transfert CDG>saint denis clients:Isabelle Massa',
    'Service non spécifié',
    'APPLE STORE R27 LE 27/12/24 REF CB.XXXXX5891',
    'APPLE STORE R315',
    'Applications - contenus - services',
    'COCACOLA BOITE SLIM 33CL',
    'COCACOLABOITE SLIM 33CL',
    "Consommation d'énergie électrique - Semaine Heures Pleines du 17/1/2024 au 1/12/2024",
    "Consommation d'énergie électrique - Week-end Heures Pleines du 17/1/2024 au 16/12/2024",
    "Consommation d'énergie électrique - Weekend Heures Creuses du 17/07/2025 au 16/08/2025",
    'Consommation d\u2019énergie électrique - Week-end Heures Pleines du 17/1/2024 au 16/12/2024',
    'Consommation d\u2019énergie électrique - Weekend Heures Creuses du 17/07/2025 au 16/08/2025',
    'Economie B.iG',
    'L2-B-Dwoop',
    'Mensualité de votre facilité de paiement pour votre équipement',
    'Ordre C',
    'Prélvements',
    'Vos autres services de tiers (**)',
    'Vos autres services et produits',
    "Pack Remote - Commande à distance vitres/toit ouvrant 360 jours, Verrouillage et déverrouillage à distance des portes 360 jours, Alerte voiturier 360 jours, Personnalisation 360 jours, Emplacement du véhicule 360 jours, Géolocalisation du véhicule 360 jours, Localiser le véhicule 360 jours, Localisation du véhicule 360 jours. Chassis : WDD2130041A652450. Ce produit est valable un an à partir de la date d'activation.",
    "Pack Remote - Commande à distance vitres/toit ouvrant 360 jours, Verrouillage et déverrouillage à distance des portes 360 jours, Alerte voiturier 360 jours, Personnalisation 360 jours, Emplacement du véhicule 360 jours, Géolocalisation du véhicule 360 jours, Localiser le véhicule 360 jours, Localisation du véhicule 360 jours. Chassis : WDD2130041A652450. Ce produit est valable un an à partir de la date d\u2019activation.",
}

before = len(data['items'])
kept = []
removed = []
for it in data['items']:
    if it.get('article_source') in TO_DELETE:
        removed.append(it.get('article_source'))
    else:
        kept.append(it)

data['items'] = kept
after = len(data['items'])
data['meta']['items_count'] = after

print('Supprimés (' + str(before - after) + ') :')
for r in removed:
    print('  - ' + r)
print('Restants : ' + str(after))

with open('base_produits_vtc_v1.json', 'w', encoding='utf-8-sig') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('Sauvegarde OK')
