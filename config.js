// Eagle Eye config. Everything here is optional except a feed and at least one lane with `live: true`.
window.EAGLE_EYE = {
  title: 'EAGLE EYE',
  // Where the numbers come from: any URL that returns the feed JSON (docs/FEED.md). Polled every 5 s.
  feed: 'demo/data.json',
  // Lanes. ring 0 = a HUNT (you go out after it, read from feed.hunts[hk]); ring 1 = a ROOST (it comes back to you,
  // read from feed.roosts[rk].rows). w = the lane's share of its ring. Exactly one lane is `live`: its funnel is the card.
  pipes: [
    {id:'job-boards', ring:0, hk:'job_boards', name:'Job boards', short:'Job boards', w:3, live:true},
    {id:'referrals',  ring:0, hk:'referrals',  name:'Referrals',  short:'Referrals',  w:1},
    {id:'cold-email', ring:0, hk:'cold_email', name:'Cold email', short:'Cold email', w:2},
    {id:'linkedin',   ring:0, hk:'linkedin',   name:'LinkedIn',   short:'LinkedIn',   w:1},
    {id:'events',     ring:0, hk:'events',     name:'Events',     short:'Events',     w:1},
    {id:'clients',    ring:1, rk:'clients',    name:'Clients',    short:'Clients',    w:1},
    {id:'network',    ring:1, rk:'network',    name:'Network',    short:'Network',    w:1},
  ],
  // The live card: STAGES is the funnel strip, KEY4 the four big numbers. Each key is a top-level number in the feed.
  stages: [['applied','applied'],['replied','replied'],['screens','screen'],['interviews','interview'],['offers','offer'],['signed','signed']],
  key4: [['applied','applied'],['replied','replied'],['interviews','interviews'],['offers','offers']],
  liveLabel: 'HUNT',
  // Optional: who works each lane and where to go to watch it (a URL opens in a named window).
  doors: {
    job_boards: {agent:'you', kind:'view', url:'', where:'no desk: plug in your own'},
  },
  hero: false,        // no per-lane detail pages in this build: a click opens the lane's sheet
  pipelines: false,
};
