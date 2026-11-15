// Eagle Eye config. Everything here is optional except a feed and at least one lane.
window.EAGLE_EYE = {
  title: 'EAGLE EYE',
  // Where the numbers come from: any URL that returns the feed JSON (docs/FEED.md). Polled every 5 s.
  feed: 'demo/data.json',
  // Lanes. ring 0 = a HUNT (you go out after it, read from feed.hunts[hk]); ring 1 = a ROOST (it comes back to you,
  // read from feed.roosts[rk].rows). w = the lane's share of its ring.
  pipes: [
    {id:'job-boards', ring:0, hk:'job_boards', name:'Job boards', short:'Job boards', w:3},
    {id:'referrals',  ring:0, hk:'referrals',  name:'Referrals',  short:'Referrals',  w:1},
    {id:'cold-email', ring:0, hk:'cold_email', name:'Cold email', short:'Cold email', w:2},
    {id:'linkedin',   ring:0, hk:'linkedin',   name:'LinkedIn',   short:'LinkedIn',   w:1},
    {id:'events',     ring:0, hk:'events',     name:'Events',     short:'Events',     w:1},
    {id:'clients',    ring:1, rk:'clients',    name:'Clients',    short:'Clients',    w:1},
    {id:'network',    ring:1, rk:'network',    name:'Network',    short:'Network',    w:1},
  ],
  // Funnel keys (top-level numbers in the feed) the eye's glow reads.
  stages: [['applied','applied'],['replied','replied'],['screens','screen'],['interviews','interview'],['offers','offer'],['signed','signed']],
  key4: [['applied','applied'],['replied','replied'],['interviews','interviews'],['offers','offers']],
  // Optional: who works each lane and where to go to watch it (a URL opens in a named window).
  doors: {
    job_boards: {agent:'you', kind:'view', url:'', where:'no desk: plug in your own'},
  },
  hero: false,        // a click opens the lane's sheet; set lanePages:true (+ laneBase) to link each lane to <laneBase>/hunt/<hk> or /roost/<rk> instead
  pipelines: false,
};
