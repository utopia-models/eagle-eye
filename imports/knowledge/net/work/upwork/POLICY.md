# Upwork policy brief: what the Terms allow (the upwork agent's first-loaded rule)

**Read this before any Upwork action.** Upwork's Trust & Safety team warned this account on 2026-11-11 (ticket
#55841136). Its words: *"Violating our Terms again can result in your account being restricted or permanently
blocked."* The operating rules that follow from this brief are in [RULES.md](RULES.md). The gate that enforces them is
`net/work/_tools/upwork/presend_check.py`, run by `voice.py check --channel upwork`.

Sources were read 2026-11-14. The legal pages were read from the Wayback snapshot of 2026-11-09
(`web.archive.org/web/20261109215657/https://www.upwork.com/legal`), because live `upwork.com/legal` returns a
Cloudflare 403 to every headless client. The Help articles were read live through the public Help Center API
(`support.upwork.com/api/v2/help_center/en-us/articles/<id>.json`). Re-read a source before you quote it to anyone.

## 1. Before a contract, everything stays on Upwork (the rule we broke)

- **User Agreement §7.2 "Communicating Through the Site; Not Sharing Contact Details"**
  (<https://www.upwork.com/legal#useragreement>): *"Prior to entering into a Service Contract, you agree to communicate
  with other Users exclusively through Upwork."* You *"will not provide your Means of Direct Contact … to any other
  User"*, and you *"will not include any Means of Direct Contact or means by which your contact information could be
  discovered in any profile, proposal, job posting, invitation, or pre-hire communication … (including in each case in
  any attached file)"*.
- **Help, "How to keep your contact information safe on Upwork"**
  (<https://support.upwork.com/hc/en-us/articles/360051749534>): *"Sharing your contact information or asking others to
  share contact information before a contract starts is against our Terms of Service, and may result in temporary
  restrictions, loss of talent badges, or permanent loss of account access."*
- **What triggered our warning** (ticket #55841136, Tyler's own reply of 2026-11-12 9:12 PM): on Nov 11 and Nov 12 we
  asked a client with no contract for his office address and, the second time, his phone number, to set up an
  in-person meeting. **Asking for theirs is the same violation as giving ours.** It also covers an in-person meeting
  before a contract, because it moves the relationship off the platform.
- **This applies to attachments and linked pages too.** A video, PDF or page that shows an email, a phone number, a
  booking link or a "contact me" line breaks §7.2.

## 2. Payments stay on Upwork for 24 months

**User Agreement §7.1 "Making Payments Through Upwork"**: *"for 24 months from the start of an Upwork Relationship
(the "Non-Circumvention Period"), you agree to use the Site as your exclusive method to request, make, and receive all
payments for work directly or indirectly with that person or arising from that relationship"*. Never talk about paying
off the platform, at any stage, with any client met on Upwork (Mohamed included).

## 3. Calls happen only through Upwork's meeting tool

- **Help, "How to use Upwork Messages for chats, updates, and meetings"**
  (<https://support.upwork.com/hc/en-us/articles/43357128336147>): *"You can meet directly from Upwork Messages using
  Upwork video meetings. Depending on availability, you may also have the option to use Zoom."*
- **Help, "How to use Zoom for video and voice meetings"** (<https://support.upwork.com/hc/en-us/articles/217698348>):
  *"Select the camera icon to start an instant meeting or the calendar icon to schedule a meeting, then choose Upwork
  video meeting."*
- Trust & Safety said the same in our ticket: *"You can use Schedule a Meeting to communicate directly through the
  site."* Never send a Meet, Zoom, Teams or Calendly link.

## 4. No automation, scraping or headless browsing of the site

- **upwork.com/legal, the "You can't interfere with our technology" list** (<https://www.upwork.com/legal#terms-of-use>):
  you may not *"use a robot, spider, scraper, or similar mechanisms on our site without written permission"*, or copy
  information found on Upwork *"without our consent (no scraping allowed)"*.
- **API & MCP Terms §5.2 "Anti-scraping, anti-automation, and circumvention"**
  (<https://www.upwork.com/legal#apimcpterms>) names *"scraping, crawling, spidering, headless browsing, web-browser
  plug-ins, optical character recognition or other image, screen, or interface-based data extraction techniques applied
  to the Upwork user interface"*.
- **What that means for us.** The seat is driven like a person: real pointer, real keyboard, a screenshot read by eye,
  at a person's pace. No Playwright, CDP, DOM reads or polling of upwork.com. Live data comes from Upwork's mail, never
  from the site (RULES.md 13-16 and 21). `upwork-seat-guard.sh` refuses the rest in the upwork session.

## 5. One account, one person, one actor

- **User Agreement §1.7 "Usernames and Passwords"** (<https://www.upwork.com/legal#usernamesandpasswords>): *"You will
  keep your username and password secret and will not share them … Each person who uses our Services must register for
  their own Account."* **§1.4**: *"only one per User"*. **§1.5**: *"You are responsible for all activity on your
  Account."*
- **The risk is stated plainly.** Tyler's account is operated by an agent on his behalf. The Terms make Tyler
  responsible for every action on it. So the seat looks and behaves like one person at one desk: one Chrome, one
  profile, one exit IP, one actor at a time, never two sessions. A login from a new device or IP is what draws a
  security review. That is why the cutover (`wi/work/specs/upwork-agent/design.md`) moves the profile and keeps the
  exit IP, once, on a day with no other change.
- **The agency.** Agency members act for the agency only from their own accounts: *"Each Agency Member must have their
  own Account to be added as an Agency Member on the Agency Account"* (User Agreement §1.4.2). Proposals go out under
  the agency **Utopia Models, Inc.** with Tyler as the member (RULES.md 18-20). Help, "How to manage your agency
  proposals and offers" (<https://support.upwork.com/hc/en-us/articles/360009524274>): *"all proposals use the
  agency's shared Connects"*, and *"An active Agency Plus membership is required to submit most proposals and accept
  offers"*.

## 6. Connects

**Help, "About Connects: costs, uses, balances, and expiration"**
(<https://support.upwork.com/hc/en-us/articles/211062898>): *"The job post shows the number of Connects needed. This is
the base proposal cost."* *"Connects cost $0.15 USD each."* *"Every Connect expires one year after the date it was
issued."* Answering a client's invitation and accepting a direct offer cost none. **Help, "Connects charges, returns,
refunds, and transaction history"** (<https://support.upwork.com/hc/en-us/articles/57221525626643>): the base cost is
returned when *"The client cancels the job before a contract is made, or Upwork removes the job post"*. A boost is a
top-four first-price auction: you pay your full bid if you are in the top four at close or the client interacts with
the boosted proposal. Which jobs get Connects is our policy, in the `upwork` skill and `plan.md`.

## 7. Proposal videos

- **Upwork Support, a person** (Mercy A., Help Center chat #55850549, 2026-11-13 12:14 MT, transcript in the upwork
  state dir `support-chat-2026-11-13-vsl.md`): *"Yes, you can attach a video to your proposal, provided the attachment
  option is available for that job post. A short 90-second MP4 video should be suitable, as long as it meets the
  platform's upload requirements. Please ensure the video does not contain personal contact information, external
  links, or any attempt to take communication or transactions outside Upwork."*
- **Help, "How to share documents, files, and more on Upwork"**
  (<https://support.upwork.com/hc/en-us/articles/360049608113>): most file types are accepted, and *"The supported file
  types are the same everywhere attachments are available (proposals, job posts, projects, messages, etc.)"*. Upwork
  publishes no proposal-specific size limit. We keep a proposal video at **25 MB or less** (an H.264/AAC MP4 of about
  90 s; [vsl-delivery-research.md](vsl-delivery-research.md)), attach it as a file, and never send a link.
- Recording stays on horus's desk and camera: the upwork agent asks horus for a take on fleetmail, gets the reviewed
  file, and attaches it by hand. A take is a recording, never a livestream.

## 8. When Upwork writes to us

Acknowledging a notice (the Terms checkbox, Done) is the only thing done alone. Never appeal, argue with, or write to
Support or Trust & Safety without the Architect, and never mention the agent setup in such a message (RULES.md 17).
Report any banner, warning, restriction, login challenge or new-device prompt to horus on fleetmail thread
`upwork-report` the minute it appears, then stop work on the seat.
