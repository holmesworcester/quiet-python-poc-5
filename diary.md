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