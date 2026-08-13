# Tasks

- [x] `vision.observe` module, gateway and observation parsing
- [x] Tests: no host in a parameter, `execute` is a coroutine, malformed refused
- [x] Optional bounded source provenance parser, with no pixel/device/topic
      forwarding and legacy compatibility
- [x] Verified against real flyto-core and a live camera gateway
- [x] Closed-loop verifier in the repository, with offline tests for its refusals
- [x] Live run from this checkout's installed wheel, recorded and digest-checkable
- [x] Discovery boundary closed: only unresolvable/incompatible flyto-core is
      swallowed, real plugin failures reach the host, discovery repeats and
      repopulates after `clear()`
- [x] Publish workflow mirroring flyto-core's, Trusted Publishing
- [x] Two earlier rounds recorded, neither accepted:
      `job_adcfb366a00a409da443a4f7` ran the six checks `.flyto/coding.yaml`
      declares and all six were green, but the job ended
      `cumulative_scope_unbounded` and wrote no change;
      `job_711ce173012247dba16dd0ac` wrote the closure documents for it and
      failed validation for an unplanned diff. Green checks and written
      documents are not acceptance, and neither round landed
- [x] Current acceptance: `job_d9d5b511348d4ce6978ea0f7`, implementation
      revision SHA-256
      `58d6c728f1915a74ed5243c958d387fcc1b695d9d77c1757f88b88df4220eb9a`, with
      its six declared checks — compile, Ruff, tests, build, Twine package
      check, Indexer strict — all passed. Acceptance of a revision is not a
      release, a tag or a publication
- [ ] PyPI pending publisher created (owner action, account sidebar)
- [ ] Tag v0.1.0 and publish
- [ ] Point the Space's camera command at `vision.observe`
- [ ] Add an explicit Pi execution integration; the runner currently rejects
      non-robotics actions such as `vision.observe`
