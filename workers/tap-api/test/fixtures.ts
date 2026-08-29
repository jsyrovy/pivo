export const BEERSTREET_FIXTURE = {
  beers: [
    {
      nazev: "Pilsner Urquell",
      nazev_pivovaru: "PU",
      styl: "Ležák",
      avb: "4,4",
      epm: "12",
      poradi: "1",
      cena04: "50",
      cena03: "",
    },
    {
      nazev: "Craft IPA",
      nazev_pivovaru: "Craft",
      styl: "IPA",
      avb: "6,0",
      epm: "14",
      poradi: "3",
      cena04: "",
      cena03: "45",
    },
    {
      nazev: "Dark Stout",
      nazev_pivovaru: "Dark",
      styl: "Stout",
      avb: "5,0",
      epm: "13",
      poradi: "2",
      cena04: "",
      cena03: "",
    },
  ],
};

export const AMBASADA_FIXTURE = `<!doctype html>
<html><body>
<table class="listek_tab">
  <tr>
    <td class="listek_tab_nazev">12° IPA</td>
    <td class="listek_tab_cena">120|80</td>
  </tr>
  <tr>
    <td class="listek_tab_popis">4,8% alc. piv. Pivovar X, India Pale Ale 0,5 l</td>
  </tr>
  <tr>
    <td class="listek_tab_nazev">Stout</td>
    <td class="listek_tab_cena">60</td>
  </tr>
  <tr>
    <td class="listek_tab_popis">5,2% alc. piv. Pivovar Y, Dry Stout 0,3 l</td>
  </tr>
  <tr>
    <td class="listek_tab_nazev">Mystery Ale</td>
    <td class="listek_tab_cena">90</td>
  </tr>
  <tr>
    <td class="listek_tab_popis">Pivovar Mystery</td>
  </tr>
  <tr>
    <td class="listek_tab_nadpis">Lahvové</td>
  </tr>
  <tr>
    <td class="listek_tab_nazev">Should not appear</td>
    <td class="listek_tab_cena">999</td>
  </tr>
  <tr>
    <td class="listek_tab_popis">Not a tap beer</td>
  </tr>
</table>
</body></html>`;

export const UZAMASTILU_FIXTURE = [
  {
    _id: "6a2c42f0ad3391234a74e956",
    order: 1,
    degree: "14°",
    brewery: "Trautenberk",
    name: "APA ",
    price05: "70",
    price03: "58",
  },
  {
    _id: "6a2c42f0ad3391234a74e95a",
    order: 5,
    degree: "12°",
    brewery: "Polička",
    name: "Záviš*Nefiltr Ležák",
    price05: "50",
    price03: "40",
  },
  {
    _id: "6a2c42f0ad3391234a74e95b",
    order: 3,
    degree: "00°",
    brewery: "Bernard",
    name: "Nealko",
    price05: "35",
    price03: "",
  },
  {
    _id: "6a2c42f0ad3391234a74e95c",
    order: 9,
    degree: "11°",
    brewery: "Should not appear",
    name: "Out of range tap",
    price05: "60",
    price03: "",
  },
];

export const TOULAVA_PIPA_FIXTURE = `Název piva,Pivní styl,Pivovar,Pozn.:,Detaily
Kamenická 12,světlý ležák ,Kynšperský zajíc,,
,,,,
Zajíc 11,Polotmavý ležák,Kynšperský zajíc,EVERGREEN,
"Hoppy lager 10",IPA,"Pivovar ""Quoted""",Novinka!,untappd.com/b/x
Birgo Mango 0,,Budvar,,
`;

export const LODOTAVA_CLOSED_FIXTURE = `Název piva,Pivní styl,Pivovar,Pozn.:,Detaily
Zahradní výčep dnes uzavřen,,,,
`;

export const AMBASADA_EMPTY_FIXTURE = `<!doctype html>
<html><body>
<table class="listek_tab">
  <tr><td class="listek_tab_nadpis">Jen lahve</td></tr>
</table>
</body></html>`;

// Every distinct style string from the 278 tap-list beers captured in
// `untappd_pairing/fixtures.json` (extracted 2026-08-27), mapped to how many beers carried it.
// Inlined instead of read from that JSON because these tests run inside workerd, which has no
// filesystem. It is the real thing, typos ("Ležák světiý") and all -- with two hand edits where
// the capture held a parser artifact rather than a style a pub ever wrote: "25l" became "Tropical
// fruit ale", what the fixed parser reads from that same beer, and "malinami a vanilkou" was
// dropped as a stale second copy of "Stout s laktozou, malinami a vanilkou", already counted below.
export const STYLE_CORPUS: Record<string, number> = {
  "Ležák světlý": 26,
  "APA": 16,
  "Ležák": 16,
  "IPA": 10,
  "NEIPA": 10,
  "Summer ale": 10,
  "Sour": 9,
  "": 8,
  "Ale": 8,
  "Fruit sour ale": 8,
  "Pale ale": 8,
  "Session IPA": 8,
  "Session NEIPA": 7,
  "Světlý ležák": 7,
  "West coast IPA": 7,
  "Hazy IPA": 5,
  "IPL": 4,
  "Pastry sour": 4,
  "Session hazy": 4,
  "Pastry sour ale": 3,
  "Single hop ale": 3,
  "Sour ale": 3,
  "American IPA": 2,
  "American pale ale": 2,
  "Fruited berliner weisse": 2,
  "Gose": 2,
  "Gose sour": 2,
  "Hazy ale": 2,
  "India pale lager": 2,
  "Juicy pale ale": 2,
  "Ležák světiý": 2,
  "Modern pale ale": 2,
  "New england IPA": 2,
  "Singl hop ale": 2,
  "Smash ale": 2,
  "Světlé výčepní": 2,
  "světlý ležák": 2,
  "Bohemian Pilsner": 1,
  "Brut IPA": 1,
  "Cold IPA": 1,
  "Cold IPA session": 1,
  "Czech amber lager": 1,
  "Czech pilsner": 1,
  "Ddh hazy IPA": 1,
  "English IPA": 1,
  "Farmhouse ale": 1,
  "Fruit IPA": 1,
  "Fruit Sour Ale": 1,
  "Fruit gose": 1,
  "Fruited pale ale": 1,
  "Fruity berliner weisse": 1,
  "German hefeweizen": 1,
  "Gluten reduced ale": 1,
  "Gluten-free session IPA": 1,
  "Gose sour - ibišek+koriandr+limeta+yuzu": 1,
  "Hazy APA": 1,
  "Helles lager": 1,
  "Hoppy saison ale": 1,
  "Ipa/dipa": 1,
  "Istrian pale ale": 1,
  "Italian pilsner": 1,
  "Kveik pale ale": 1,
  "Kyseláč": 1,
  "Lehký sour ale s bezovým květem a maracujou": 1,
  "Mexican session cold IPA": 1,
  "Milkshake NEIPA - raspberry": 1,
  "Modern Pale Ale": 1,
  "Nefiltr ležák": 1,
  "New zealand hazy ale": 1,
  "New zealand pale lager": 1,
  "Ochucené tm. pivo": 1,
  "Ochucený ale": 1,
  "Ochucený ležák": 1,
  "Pale Ale": 1,
  "Pilsner": 1,
  "Pilsner - czech": 1,
  "Pilsner - new zealand": 1,
  "Pilsner czech": 1,
  "Polotmavý ležák": 1,
  "Red APA": 1,
  "Rotbier": 1,
  "SMASH ležák sv.": 1,
  "Sessiin NEIPA": 1,
  "Session IPA mosaic": 1,
  "Session kveik IPA": 1,
  "Session pale ale": 1,
  "Sour Ale w/ Blackcurrant": 1,
  "Sour berlin weisse": 1,
  "Stout s laktozou, malinami a vanilkou": 1,
  "Summer Ale": 1,
  "Sv. ležák": 1,
  "Tmavý porter ochuc. třešněmi": 1,
  "Tropical fruit ale": 1,
  "Výroční ležák 6 let": 1,
  "Weizen": 1,
  "Weizenbier": 1,
  "West Coast IPA": 1,
  "West coast IPA w/ juniper": 1,
  "White IPA": 1,
  "White session IPA": 1,
  "Witbier": 1,
};

export const AMBASADA_LONG_DESC_FIXTURE = `<!doctype html>
<html><body>
<table class="listek_tab">
  <tr>
    <td class="listek_tab_nazev">Long One</td>
    <td class="listek_tab_cena">80</td>
  </tr>
  <tr>
    <td class="listek_tab_popis">4,0% alc. piv. Pivovar s Velmi Dlouhym Nazvem a Popisem, Okres Hodne Velmi Daleko od Centra, Nadmorska Vyska 800 m, Pale Ale with various adjuncts</td>
  </tr>
</table>
</body></html>`;
