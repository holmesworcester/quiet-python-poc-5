- LLM made the same mistake of mixing core and protocols again
- This time I'm trying an approach with no tests and instead just making sure envelopes travel through the pipeline
- Starting with commands seems like a good rule to keep it from seeding data artificially
- Building up to an outgoing envelope seems like a good way to get an incoming envelope
- But there's a lot of boilerplate if we're working at the level of envelopes
- So I'm jumping right into making an api and demo.py so it can do tests via higher level commands, with a frontend that tracks state.

had to give these instructions:

the project feels disorganized. event_types should have all of our types as subdirectories.     │
│   inside each directory, we have subfolders: commands, queries, projectors and validators.        │
│   inside those folders we have py files for the commands (etc) most related to that event type.   │
│   prefer small single purpose files that map to API calls. \                                      │

│   also follow poc-3 and make demo and demo-cli **the same** code so that there is as much parity  │
│   as possible between the CLI and TUI behavior as we make changes. CLI output should directly     │
│   match TUI final state, and CLI commands should match as if a TUI user had done those same       │
│   commands.  

- where to locate the event store is a little weird. i'm putting it in a handler now, but then it's a bit weird to figure out where it fits in the pipeline. this should be easy to change though. 

- TODO: make most validators not duplicate stuff from the generic validate step
- TODO: fix bug in poc-3 groups

Ways to challenge the design:

- Add files but in the less-efficient way where blocks are still signed, to test the file storage efficiency part without worrying about signature inefficiency (test if special casing is needed)
- Make a bittorrent-like UI using our proposed file transfer scheme (perf for large-ish files!)
- Make a real holepunching system where non-NATed peers help NATed peers connect.
- maybe: make a bittorrent-like protocol under the hood (blocks, hashes, give/get, etc) 
- Make a todo-mvc or Trello
- Make something like Telegram channels, or shared ownership of a Twitter feed, community can post comments, peers participating in two communtiies and acting as the bridge between them.
- Tables at an event. Proposals, post its, votes, approval voting. 
- Replicate the reddit moderation interface
- closed-world twitter...  AND with features for posting as a team? They would follow others and have their mentions and would decide together what to repost, and if to reword. tweeting, debating what to tweet, working through DMs, adding someone to the group, removing someone from the group, etc. 
- Vetting new community members with an application form 
- ban together flow. Curate ban lists for others to use. 
- Real time, performance, permissioning