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

export const AMBASADA_EMPTY_FIXTURE = `<!doctype html>
<html><body>
<table class="listek_tab">
  <tr><td class="listek_tab_nadpis">Jen lahve</td></tr>
</table>
</body></html>`;

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
