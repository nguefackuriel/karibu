const pptxgen = require("./node_modules/pptxgenjs");

const INK = "1C1A17", WHITE = "FFFFFF", GREEN = "1F6F5C", AMBER = "A06A12";
const BODY = "3D3832", MUTED = "6B6459", LINE = "DFD9CE";
const SOFT = "E8F2EE", DARKCARD = "2A2622", DARKLINE = "3D3832";
const PALE = "8FBFAF", DARKBODY = "B9B2A6";
const H = "Cambria", T = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // 13.33 x 7.5
pres.author = "Team LeKontinent";
pres.title = "Karibu";

const M = 0.65, W = 13.33 - M * 2;

const txt = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0 }, o));

function title(s, text, color) {
  txt(s, text, { x: M, y: 0.5, w: W, h: 1.35, fontFace: H, fontSize: 32, bold: true,
                 color: color || INK, valign: "top", lineSpacing: 38 });
}

// ---------------------------------------------------------------- 1. cover
{
  const s = pres.addSlide();
  s.background = { color: INK };
  txt(s, "WORLD BANK SMALL AI FOR DEVELOPMENT   ·   TOURISM",
      { x: M, y: 1.85, w: W, h: 0.3, fontFace: T, fontSize: 12, bold: true, charSpacing: 2, color: PALE });
  txt(s, "Karibu", { x: M, y: 2.2, w: W, h: 1.4, fontFace: H, fontSize: 72, bold: true, color: WHITE });
  txt(s, "A guesthouse owner with a basic phone takes a booking from a Korean visitor, in French, for the price of one text message.",
      { x: M, y: 3.7, w: 9.6, h: 1.3, fontFace: T, fontSize: 20, color: "EDE7DC", lineSpacing: 30 });
  txt(s, "Team LeKontinent   ·   3 and 4 October 2026",
      { x: M, y: 6.6, w: W, h: 0.3, fontFace: T, fontSize: 11, color: DARKBODY });
  s.addNotes("Open on the promise, not on the team. Read the line out loud, then move on. Twenty seconds.");
}

// ---------------------------------------------------------------- 2. problem
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  title(s, "The people who receive visitors do not exist online");
  const paras = [
    "Around parks, waterfalls and heritage sites, the guesthouses and guides who actually host people have no website and no way to be booked.",
    "Every booking platform assumes a smartphone, a steady connection and a bank card. Most hosts have none of the three.",
    "So the money stops with agents in the capital, and the tourism office has no idea what happens on its own ground."
  ];
  paras.forEach((p, i) => txt(s, p, { x: M, y: 2.05 + i * 1.35, w: 6.5, h: 1.2,
    fontFace: T, fontSize: 15, color: BODY, lineSpacing: 23 }));

  s.addShape(pres.ShapeType.roundRect, { x: 7.65, y: 2.0, w: 5.03, h: 3.95,
    fill: { color: "F7FAF9" }, line: { color: LINE, width: 1 }, rectRadius: 0.12 });
  txt(s, "WHO WE BUILT IT FOR", { x: 8.05, y: 2.35, w: 4.2, h: 0.3,
    fontFace: T, fontSize: 11, bold: true, charSpacing: 2, color: AMBER });
  txt(s, "Nathalie rents two rooms in Bafang, near the Metché falls.",
    { x: 8.05, y: 2.75, w: 4.25, h: 1.3, fontFace: H, fontSize: 21, bold: true, color: INK, lineSpacing: 28 });
  txt(s, "She has a phone with buttons. She reads a little. Visitors walk past her door on the way to the falls and she has no way to reach them.",
    { x: 8.05, y: 4.1, w: 4.25, h: 1.6, fontFace: T, fontSize: 14, color: MUTED, lineSpacing: 22 });
  s.addNotes("Nathalie is the host in our story. Do not read the three paragraphs out loud, just land the last sentence: the money stops in the capital.");
}

// ---------------------------------------------------------------- 3. exchange
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  title(s, "One booking, four messages");
  const rows = [
    ["Visitor", "web page, Korean",
     "10월 12일부터 2박, 2명 가능한가요? 아침 식사 포함인가요?",
     WHITE, INK, true],
    ["Host", "SMS, French",
     "Karibu: demande 2n 12-14 oct, 2 pers +petit dej. Total 16000 FCFA. Repondre 1=OUI 2=NON 3=AUTRE DATE",
     SOFT, "13453A", false],
    ["Host replies", "one character", "1", GREEN, WHITE, false],
    ["Visitor", "web page, Korean",
     "확정되었습니다. 10월 12일-14일, 2명, 조식 포함, 16000 FCFA. 예약번호 59UG.",
     WHITE, INK, true]
  ];
  let y = 1.85;
  rows.forEach(([label, sub, body, bg, fg, bordered]) => {
    const h = 0.95;
    txt(s, label, { x: M, y: y + 0.16, w: 2.1, h: 0.3, fontFace: T, fontSize: 14, bold: true, color: INK });
    txt(s, sub, { x: M, y: y + 0.46, w: 2.1, h: 0.3, fontFace: T, fontSize: 12, color: MUTED });
    s.addShape(pres.ShapeType.roundRect, { x: 2.95, y: y, w: 9.73, h: h,
      fill: { color: bg }, line: bordered ? { color: LINE, width: 1 } : { color: bg, width: 1 },
      rectRadius: 0.1 });
    txt(s, body, { x: 3.2, y: y + 0.13, w: 9.25, h: h - 0.26,
      fontFace: T, fontSize: 14, color: fg, lineSpacing: 21, valign: "middle" });
    y += h + 0.22;
  });
  txt(s, "106 characters. One SMS segment. No app, no smartphone, no bank card.",
    { x: M, y: 6.6, w: W, h: 0.3, fontFace: T, fontSize: 12, color: MUTED });
  s.addNotes("This is the slide to slow down on. Show the real thing running if you can. Point at the reply: the whole interface for the host is one character.");
}

// ---------------------------------------------------------------- 4. how
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  title(s, "Everything runs on one machine in the tourism office");
  const cards = [
    ["Visitor", "Any language, on a plain web page. No account, no app.", WHITE, INK],
    ["The hub", "A laptop today, a Raspberry Pi in the field. Rules, a 1B model, speech recognition, SQLite.", "F7FAF9", GREEN],
    ["Host", "A phone with buttons. SMS in French, answers with one digit.", WHITE, INK]
  ];
  const cw = 3.64, gap = 0.555;
  cards.forEach(([h1, body, bg, fg], i) => {
    const x = M + i * (cw + gap);
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.15, w: cw, h: 2.2,
      fill: { color: bg }, line: { color: LINE, width: 1 }, rectRadius: 0.12 });
    txt(s, h1, { x: x + 0.32, y: 2.45, w: cw - 0.64, h: 0.4, fontFace: T, fontSize: 18, bold: true, color: fg });
    txt(s, body, { x: x + 0.32, y: 2.92, w: cw - 0.64, h: 1.3, fontFace: T, fontSize: 13.5, color: MUTED, lineSpacing: 21 });
  });
  [0, 1].forEach(i => {
    const x = M + cw + i * (cw + gap);
    s.addShape(pres.ShapeType.line, { x: x + 0.12, y: 3.25, w: gap - 0.24, h: 0,
      line: { color: AMBER, width: 2, endArrowType: "triangle", beginArrowType: i === 1 ? "triangle" : "none" } });
  });
  txt(s, "The tourism office gets a dashboard and an open catalogue, so any destination portal can list these rooms. No part of taking a booking touches the internet.",
    { x: M, y: 4.85, w: 11.6, h: 1.0, fontFace: T, fontSize: 16, color: BODY, lineSpacing: 25 });
  s.addNotes("The point of this slide is that nothing calls out to a cloud. Say it plainly: if the connection drops, the hub keeps taking bookings.");
}

// ---------------------------------------------------------------- 5. rules
{
  const s = pres.addSlide();
  s.background = { color: INK };
  title(s, "The model never reads a date", WHITE);
  txt(s, "We tested the small model on real messages before trusting it with anything. Twice it failed in a way that would put a host on the wrong doorstep.",
    { x: M, y: 1.75, w: 11.4, h: 0.7, fontFace: T, fontSize: 16, color: "D8D1C6", lineSpacing: 25 });
  const fails = [
    ["We asked it to read", "“du 20 au 23 octobre”", "It answered the 23rd. The guest arrives three days late."],
    ["We asked about a message with no mention of food", "It said breakfast was included", "Every single time. The host loses money on a meal nobody ordered."]
  ];
  fails.forEach(([lab, quote, out], i) => {
    const x = M + i * 6.2;
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.65, w: 5.83, h: 2.15,
      fill: { color: DARKCARD }, line: { color: DARKLINE, width: 1 }, rectRadius: 0.12 });
    txt(s, lab, { x: x + 0.32, y: 2.9, w: 5.2, h: 0.5, fontFace: T, fontSize: 12.5, color: "C99A3E", lineSpacing: 18 });
    txt(s, quote, { x: x + 0.32, y: 3.42, w: 5.2, h: 0.55, fontFace: T, fontSize: 18, bold: true, color: WHITE });
    txt(s, out, { x: x + 0.32, y: 4.0, w: 5.2, h: 0.65, fontFace: T, fontSize: 13.5, color: DARKBODY, lineSpacing: 20 });
  });
  txt(s, "So dates, nights, guests, prices and meals are read by rules, in Korean, French and English. The model only fills what the rules leave blank, and it can never overwrite them. When neither can read a date, Karibu says so instead of guessing.",
    { x: M, y: 5.15, w: 11.9, h: 1.2, fontFace: T, fontSize: 16.5, color: WHITE, lineSpacing: 26 });
  s.addNotes("This is the slide that separates us from the other teams. Most will hand the whole message to a model. Say the quote out loud and let it sit for a second.");
}

// ---------------------------------------------------------------- 6. numbers
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  title(s, "Measured on a laptop, no GPU, no cloud");
  const rows = [
    ["Rules read a whole message", "0.1 ms"],
    ["The model fills a blank the rules left", "2.6 s"],
    ["Speech turned into a finished listing", "3.7 s"],
    ["Longest message we send a host", "113 characters, 1 segment"],
    ["Cost of one completed booking", "about 0.08 USD"],
    ["Hub for one tourism office", "about 80 USD, once"],
    ["Internet needed to take a booking", "none"]
  ];
  const head = [
    { text: "WHAT", options: { bold: true, color: MUTED, fontSize: 11, charSpacing: 2 } },
    { text: "MEASURED", options: { bold: true, color: MUTED, fontSize: 11, charSpacing: 2, align: "right" } }
  ];
  const body = rows.map(([a, b]) => ([
    { text: a, options: { color: BODY, fontSize: 15 } },
    { text: b, options: { color: INK, fontSize: 15, bold: true, align: "right" } }
  ]));
  s.addTable([head, ...body], {
    x: M, y: 1.95, w: W, colW: [7.6, 4.43], fontFace: T,
    border: [{ type: "none" }, { type: "none" }, { type: "solid", color: LINE, pt: 1 }, { type: "none" }],
    rowH: 0.48, valign: "middle", margin: [4, 6, 4, 6]
  });
  txt(s, "The language model is 815 MB on disk. Every figure can be rerun with one command in the repository.",
    { x: M, y: 6.6, w: W, h: 0.3, fontFace: T, fontSize: 12, color: MUTED });
  s.addNotes("Do not read the table. Pick two numbers: a tenth of a millisecond, and eight cents a booking. The rest is there for the judges to check.");
}

// ---------------------------------------------------------------- 7. tradeoffs
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  title(s, "What we gave up to fit inside one text message");
  const items = [
    ["160 characters, not a screen", "Every question we ask the host is closed and every answer is one character. We lose choice and we gain a message that costs one segment and shows on any handset."],
    ["Rules, not a bigger model", "Rules do not generalise. Each language had to be written by hand. In exchange the dates are right and the answer comes back in a millisecond."],
    ["The host makes them wait", "Confirmation is not instant. The visitor is told to allow two hours, and the request expires after that so nobody is left hanging."],
    ["Three languages, not a hundred", "Korean, French and English are read by rule. A fourth language is a small table, not a retrained model."],
    ["No booking is final without a person", "The model can be wrong, so the host is the check. That is slower than confirming automatically, and it is the only version worth putting in front of a real guesthouse."]
  ];
  let y = 1.85;
  items.forEach(([h1, body], i) => {
    txt(s, h1, { x: M, y: y + 0.04, w: 4.3, h: 0.7, fontFace: T, fontSize: 15, bold: true, color: INK, lineSpacing: 21 });
    txt(s, body, { x: 5.15, y: y, w: 7.5, h: 0.85, fontFace: T, fontSize: 13.5, color: BODY, lineSpacing: 20 });
    if (i < items.length - 1) {
      s.addShape(pres.ShapeType.line, { x: M, y: y + 0.92, w: W, h: 0, line: { color: LINE, width: 1 } });
    }
    y += 1.02;
  });
  s.addNotes("The brief scores this criterion explicitly and most teams will skip it. Do not apologise for any of these. Each one is a choice, and say so.");
}

// ---------------------------------------------------------------- 8. ask
{
  const s = pres.addSlide();
  s.background = { color: INK };
  txt(s, "BOTH DIRECTIONS ALREADY WORK", { x: M, y: 1.3, w: W, h: 0.3,
    fontFace: T, fontSize: 12, bold: true, charSpacing: 2, color: PALE });
  txt(s, "A Korean message went in and a French text message came back out, over a real network.",
    { x: M, y: 1.75, w: 11.5, h: 1.6, fontFace: H, fontSize: 36, bold: true, color: WHITE, lineSpacing: 46 });
  const cards = [
    ["What we want", "One tourism office and ten hosts, for one season."],
    ["What it costs them", "One hub of about 80 USD, and eight cents a booking."],
    ["What we measure", "Bookings that reach the host, and money that stays in the village."]
  ];
  const cw = 3.64, gap = 0.555;
  cards.forEach(([h1, body], i) => {
    const x = M + i * (cw + gap);
    s.addShape(pres.ShapeType.roundRect, { x, y: 3.85, w: cw, h: 1.85,
      fill: { color: DARKCARD }, line: { color: DARKLINE, width: 1 }, rectRadius: 0.12 });
    txt(s, h1, { x: x + 0.3, y: 4.1, w: cw - 0.6, h: 0.35, fontFace: T, fontSize: 15, bold: true, color: WHITE });
    txt(s, body, { x: x + 0.3, y: 4.52, w: cw - 0.6, h: 1.0, fontFace: T, fontSize: 13.5, color: DARKBODY, lineSpacing: 20 });
  });
  txt(s, "Team LeKontinent   ·   github.com/nguefackuriel/karibu",
    { x: M, y: 6.6, w: W, h: 0.3, fontFace: T, fontSize: 11, color: DARKBODY });
  s.addNotes("End on the ask, not on thanks. Name the tourism office out loud if you have one by then.");
}

pres.writeFile({ fileName: "karibu-deck.pptx" }).then(f => console.log("wrote", f));
