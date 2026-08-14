# Restauration Sources Manquantes V1

- dry_run: `false`
- generated_at: `2026-05-06T01:26:11.551160Z`
- source_db_factures: `abt3`

## btp
- partitions_scanned: `10`
- items_changed: `168`
- invoice_ids_added: `50`
- partitions_filled: `0`
- ape_filled: `164`
- base_produits_btp_v1.json: changed=`84` ids_added=`25` partitions_filled=`0` ape_filled=`82`
- base_produits_btp_v1_with_accounts.json: changed=`84` ids_added=`25` partitions_filled=`0` ape_filled=`82`

Exemples :
- `Sac a gravat tissé 60x100cm paquet de 10 pièces`
  avant_ids=`[]`
  apres_ids=`['fr_bd_879788230:3c7f34a4-61d2-4bed-9522-411847b845d2', 'fr_bd_879788230:02271126-6f0d-44d9-a408-ee97c881f03f']`
  avant_partitions=`['fr_bd_842785719', 'fr_bd_879788230']`
  apres_partitions=`['fr_bd_842785719', 'fr_bd_879788230']`
  avant_ape=`['4399C']`
  apres_ape=`['4399C']`
- `Passerelle`
  avant_ids=`[]`
  apres_ids=`['fr_bd_914837463:98d85f4f-e9bc-40c4-a080-bcc72053ba9c', 'fr_bd_914837463:e32b38db-14e0-416b-b421-16a4cf6db045', 'fr_bd_914837463:3398281c-342f-4b84-b559-f94543ecd3fb']`
  avant_partitions=`['fr_bd_914837463']`
  apres_partitions=`['fr_bd_914837463']`
  avant_ape=`['4321A']`
  apres_ape=`['4321A']`
- `vanne thermostatique connectée`
  avant_ids=`[]`
  apres_ids=`['fr_bd_914837463:98d85f4f-e9bc-40c4-a080-bcc72053ba9c', 'fr_bd_914837463:e32b38db-14e0-416b-b421-16a4cf6db045', 'fr_bd_914837463:3398281c-342f-4b84-b559-f94543ecd3fb']`
  avant_partitions=`['fr_bd_914837463']`
  apres_partitions=`['fr_bd_914837463']`
  avant_ape=`['4321A']`
  apres_ape=`['4321A']`
- `Passerelle( avec ethernet)`
  avant_ids=`[]`
  apres_ids=`['fr_bd_914837463:3398281c-342f-4b84-b559-f94543ecd3fb', 'fr_bd_914837463:cef51204-e23d-4f11-93ad-0e4612a8195a', 'fr_bd_914837463:6129859d-f805-45cb-9383-ac7d63d6f98b']`
  avant_partitions=`['fr_bd_914837463']`
  apres_partitions=`['fr_bd_914837463']`
  avant_ape=`['4321A']`
  apres_ape=`['4321A']`
- `PALETTE LUSSIANA`
  avant_ids=`[]`
  apres_ids=`[]`
  avant_partitions=`['fr_bd_842785719']`
  apres_partitions=`['fr_bd_842785719']`
  avant_ape=`[]`
  apres_ape=`['4399C']`

## boulangerie
- partitions_scanned: `4`
- items_changed: `206`
- invoice_ids_added: `460`
- partitions_filled: `18`
- ape_filled: `48`
- base_produits_boulangerie_v1.json: changed=`103` ids_added=`230` partitions_filled=`9` ape_filled=`24`
- base_produits_boulangerie_v1_with_accounts.json: changed=`103` ids_added=`230` partitions_filled=`9` ape_filled=`24`

Exemples :
- `CANADIENNE D'OEUFS X180`
  avant_ids=`[]`
  apres_ids=`['fr_bd_519665103:9d697358-768f-4d30-87bc-6bd1ee15dc92']`
  avant_partitions=`[]`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `FARINE DE POIS CHICHE`
  avant_ids=`['fr_bd_519665103:7cb84be9-5186-4599-9ced-21af43adba4f']`
  apres_ids=`['fr_bd_519665103:7cb84be9-5186-4599-9ced-21af43adba4f', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `Farine Pois Chiches 500g`
  avant_ids=`['fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  apres_ids=`['fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `HUILE D'OLIVE EL HORA`
  avant_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e']`
  apres_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `Huile d'olive TASSOURT 1L`
  avant_ids=`['fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  apres_ids=`['fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`

## boucherie
- partitions_scanned: `5`
- items_changed: `410`
- invoice_ids_added: `954`
- partitions_filled: `14`
- ape_filled: `78`
- base_produits_boucherie_v1.json: changed=`205` ids_added=`477` partitions_filled=`7` ape_filled=`39`
- base_produits_boucherie_v1_with_accounts.json: changed=`205` ids_added=`477` partitions_filled=`7` ape_filled=`39`

Exemples :
- `FILM ALIMENTAIRE 45CM X 300M EN BOITE DISTRIBUTRICE AVEC LAME`
  avant_ids=`['fr_bd_519665103:2b654cc7-770b-4ca9-8013-83c3e2e8795f']`
  apres_ids=`['fr_bd_519665103:2b654cc7-770b-4ca9-8013-83c3e2e8795f']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `CUISSE DE POULET FERMIER HALAL`
  avant_ids=`['fr_bd_519665103:36b6c940-ca33-489a-90f5-5b1fdbdf25c2', 'fr_bd_519665103:06b57208-10e0-4d08-899a-27ec6b8b083d', 'fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d']`
  apres_ids=`['fr_bd_519665103:36b6c940-ca33-489a-90f5-5b1fdbdf25c2', 'fr_bd_519665103:06b57208-10e0-4d08-899a-27ec6b8b083d', 'fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d']`
  avant_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  apres_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `BASSE SANS POITRINE DE VEAU`
  avant_ids=`['fr_bd_519665103:1fa088a2-1f5a-41b5-a5c7-277d685679c8', 'fr_bd_519665103:8a93439c-88b3-4da1-ac86-b5bc937f207c', 'fr_bd_519665103:632a6b9e-585f-48cd-b57f-d4a8347c0385']`
  apres_ids=`['fr_bd_519665103:1fa088a2-1f5a-41b5-a5c7-277d685679c8', 'fr_bd_519665103:8a93439c-88b3-4da1-ac86-b5bc937f207c', 'fr_bd_519665103:632a6b9e-585f-48cd-b57f-d4a8347c0385']`
  avant_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  apres_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `FILET DE POULET FERMIER HALAL`
  avant_ids=`['fr_bd_519665103:06b57208-10e0-4d08-899a-27ec6b8b083d', 'fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d', 'fr_bd_519665103:3b9a3d8b-8637-4c29-9738-7c118f0dcfd9']`
  apres_ids=`['fr_bd_519665103:06b57208-10e0-4d08-899a-27ec6b8b083d', 'fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d', 'fr_bd_519665103:3b9a3d8b-8637-4c29-9738-7c118f0dcfd9']`
  avant_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  apres_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `COQUELET HALAL`
  avant_ids=`['fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d', 'fr_bd_519665103:3b9a3d8b-8637-4c29-9738-7c118f0dcfd9', 'fr_bd_519665103:834e8468-4ed8-419d-a6bf-e0c28b5f330b']`
  apres_ids=`['fr_bd_519665103:13d284e3-b4bb-41a3-9c12-0dcd6b5dba4d', 'fr_bd_519665103:3b9a3d8b-8637-4c29-9738-7c118f0dcfd9', 'fr_bd_519665103:834e8468-4ed8-419d-a6bf-e0c28b5f330b']`
  avant_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  apres_partitions=`['fr_bd_519665103', 'fr_bd_828612630', 'fr_bd_837602275']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`

## restaurant
- partitions_scanned: `4`
- items_changed: `290`
- invoice_ids_added: `580`
- partitions_filled: `2`
- ape_filled: `88`
- base_produits_restaurant_v1.json: changed=`145` ids_added=`290` partitions_filled=`1` ape_filled=`44`
- base_produits_restaurant_v1_with_accounts.json: changed=`145` ids_added=`290` partitions_filled=`1` ape_filled=`44`

Exemples :
- `FILM ALIMENTAIRE 45CM X 300M EN BOITE DISTRIBUTRICE AVEC LAME`
  avant_ids=`['fr_bd_519665103:2b654cc7-770b-4ca9-8013-83c3e2e8795f']`
  apres_ids=`['fr_bd_519665103:2b654cc7-770b-4ca9-8013-83c3e2e8795f']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `HARISSA 1/2`
  avant_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4']`
  apres_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `HARISSA 1/6`
  avant_ids=`['fr_bd_519665103:7cb84be9-5186-4599-9ced-21af43adba4f', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4', 'fr_bd_519665103:64cfb123-6244-4010-9c48-8a3e3d1d5d0b']`
  apres_ids=`['fr_bd_519665103:7cb84be9-5186-4599-9ced-21af43adba4f', 'fr_bd_519665103:5e30287f-8daa-4473-a379-15194a0551d4', 'fr_bd_519665103:64cfb123-6244-4010-9c48-8a3e3d1d5d0b']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `HARISSA TUBE 70g`
  avant_ids=`['fr_bd_519665103:75334608-dc1c-4605-bb88-1b7ca0b5b8fd', 'fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  apres_ids=`['fr_bd_519665103:75334608-dc1c-4605-bb88-1b7ca0b5b8fd', 'fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:c0316ef0-e388-42e0-9b06-b9db2e524618']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`
- `OLIVE VERTE DENOYAUTEE`
  avant_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:e4345936-ed42-4d14-85d1-69bd52325db9', 'fr_bd_519665103:65afe443-ded1-4f32-a87e-3e226e82b376']`
  apres_ids=`['fr_bd_519665103:cbe599ff-d66e-43f4-adcb-ac7ef27afa1e', 'fr_bd_519665103:e4345936-ed42-4d14-85d1-69bd52325db9', 'fr_bd_519665103:65afe443-ded1-4f32-a87e-3e226e82b376']`
  avant_partitions=`['fr_bd_519665103']`
  apres_partitions=`['fr_bd_519665103']`
  avant_ape=`[]`
  apres_ape=`['4722Z']`

