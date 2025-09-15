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

Todo: when we add removal, we need to check if removed as a last step in the pipeline, before projecting, and all removals must go in a queue that is processed serially by the remove checker, which also purges things. 

having commands use a pipeline instead of generating right off the bat is challenging:
1. they often need to provide an id in a response (easy solution: return id's)
2. they often need to provide query results in a response (easy solution: let them specify a query and run it after projecting all envelopes, and return that)
3. they often need to make multiple events that reference each other. (maybe: use placeholder refs that get filled in by update deps in the looping pipeline process???'')'

- ended up using placeholder deps and resolve_deps to fill them in as the events got signed and encrypted and stored
- with user events there was the awkward issue that we didn't have the invite event yet, so we couldn't test that our join operation was successful. since we are assuming that invite links are valid I exempted us from requiring the invite event in the self-signed case, but that's a bit weird and could be refined. maybe not validating until real join is the right answer.
- we couldn't run the whole pipeline and test that it filled in correctly without having a test that actually checked the api results (and ran the whole pipeline loop to get them) so I made command tests check the API results too. this makes them more complicated but is necessary to capture the functionality and closer to a real integration test. we can still have the simpler envelope-only tests
- some commands can only be tested well with scenario tests if we want to run them through the whole pipeline because we need to make tests earlier. 

decisions: we keep protocol/quiet/jobs.yaml. we don't have protocol/quiet/jobs and we extend commands to be able to do a query first and then operate on the query. then we make queries that the sync-request job and the sync-request event projector can use. this is also a bit weird. we'll have to modify projectors to be able to emit envelopes other than deltas (outgoing ones.)  

better decision: no jobs.yaml. jobs handler. reflector handler. both can query and emit envelopes. jobs are triggered by time and provided state persisted by the job handler (e.g. for bloom window). reflectors are triggered by events and we don't need state for those yet but maybe we will.  

infinite loops are a problem with our current event bus system.
but it's easy to add some protection against it and limit to 100 tries e.g.  