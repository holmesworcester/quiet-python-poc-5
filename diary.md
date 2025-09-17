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
but it's easy to add some protection against it and limit to 100 tries e.g. -- did this and it should now emit a runtime error.

- we decided we'd focus on closed-world twitter with team-managed accounts
- and audio/video screen sharing with annotations

we might want to flip the dependency and make group one of the refs of a network event, so that a network can name a main group so it's unambiguous. other groups could name network-id's. i should think about this because it's sensitive. 

there's some ambiguity about what to do with id's for identity events because they're an exception, because they aren't encrypted or shared. and should we store them in the identity table or the event store. 
bootstrapping these things is difficult to reason about and always a bit of a puzzle. it would be nice if the framework was very opinionated and provided that itself.

what's the relationship between identity, peer, user, and network.

for the first user, it sort of makes sense for the identity and peer and user and first group to be created first, and mentioned in network. that way, once you have the network id, you know what the first group is. and you can validate the user just based on them being included in the network. we could create an admin group too and include that in network as well. then there's a symmetry with joining where the user event refers to invite and network and you can validate that it has all the things. it also creates more symmetry with creating and joining a network, except that the user is created when joining. 

i should really understand resolve_deps for placeholder deps and how that works.

Auth is a tangle and it's good to proceed from a rock-solid document. 

i'm really not convinced about where to put identities. 
should pubkey get resolved as a dependency so that sign just has the pk in the envelope?
shoudl we go back to having an identity event like any other with its own table and we just don't share it and exempt it from usual checks?
should identity be a handler and create identity is an envelope that gets emitted by a command, and then filled in by the handler?

getting the TUI demo working is proving to be inefficient. but getting the CLI version working is much easier, because LLMs can see what they're doing, and because we're not managing state in the same way. 
there might be some value in getting a web demo working so that we can test that the API is comfortable and realistic
one intuition i have is to push on the CLI demo so that we have a perfect repl for testing things.
we shouldn't use names as identifiers because the API doesn't. we should use id's. commands like /switch or /group or /channel should show me a set of numbered choices (sorted by created_at_ms) and I pick one
this way you can guess at the choice in CLI with a number
we should have a $last-created shortcut for the invite command where you can just use the last created invite.
/state should show the state of all panels (e.g. which channel is active, which user, which network, etc.) and then /views could show a text illustration of all panels. 
being able to see a log of how envelopes flow through handlers would be interesting

maybe i should focus directly on the commands first and not worry about the demo as much yet. 
i don't like how pipeline runner has tons of code in it for resolving placeholder id's. this should fit into resolve_deps exclusively. maybe the issue is they don't have an event_id yet?

maybe there's a better way of chaining the creation of events. 

TODO: if handler loading order matters at all, that's bad, because it could be OS or timing specific. handler loading order shouldn't matter in the current formulation. We should make ordering deterministic, arbitrary.
TODO: standardize naming of fields on all event types -- it might be good to centralize event/envelope creation somewhere so events only think about their own bespoke fields and list their deps.

i think part of the problem here is that we are cramming together our pure
params=>envelopes logic with our "chain and present to API" logic. one thing we could
do is add an api.py or api_ops.py for each event and leave commands to be purely for
functions that consume params and emit envelopes. then we can do some mumbo jumbo on
the core side so that devs can write simple chains in api.py that create events, get
id's, create more events with those id's, return a query, etc. in the most dead-simple
way where everything is encapsulated. there also seems like something similar going
on with jobs and reflectors, where we need to run a query and emit envelopes in
the jobs case, or we need to receive an envelope, run a query, and emit envelopes
in the reflectors case. are these cases so different? could we combine them? e.g.
sync-request would have a command that takes params (dest_ip, transit_key, etc) and
events and adds the correct data to outgoing envelopes. and a job could query the
window for id's, apply the bloom, query for events, and pass those to the command,
perhaps one by one. let's consider this!

there's an intuition gnawing at me that flows could be simpler. like you could emit an envelope that said what its chain was, or what its relationship was to future envelopes. buuut. that's probably harder to express. 

will we have any commands that do multiple things, beyond what is in flows? or will they all be "create" now? if so, maybe we should just call commands "create".

create seems very light for a cateogry of thing. we could just use a protocol-provided emit_envelope function within 

the idea of chaining together things that use the pipeline and get an id or final envelope from it, and can query, for things where we don't really care about concurrency, is really useful. it lets us have this opinionated pipeline thing for organizing the way stuff gets made and validated and keeping that under control, while also having a way to just write normal programs for things. reflectors, jobs, and commands all ended up being this: "flows". I like the name flows but we could just call them commands to keep with CQRS. (though I think ours do a bit more because they can query too.)   