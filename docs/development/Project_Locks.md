# Native project locks

Current contract after RECOVERY-REMOVAL-006 and 18.w/18.x. See
[Interrupted writes and separate Git restart](Interrupted_Writes.md).

`specroad.changes.project_lock` is an explicit process-local context manager
for cooperating native Linux writers and operational clients. They share the
nonblocking `flock` on the project root directory inode. Unsupported native
locking fails closed. This is not a distributed lease or a sandbox against
independent writers. Legacy `kind="recovery"` requests are rejected before I/O.

The mode-0600 owner record `.specroad/locks/project.json` binds the original
lock identity, root inode, project, process/start/host observations, command,
request and transaction. Unknown observations remain unknown. Writer admission
checks configuration, original root and unresolved operational entries. Handles
cannot be copied, serialized or released by a forked child.

A live writer removes only its exact owner record after its normal completion
permits release. Interrupted publication retains the guard and owner. No stale
record is stolen automatically, and a foreign replacement is never removed.

`inspect_project_lock` observes and rechecks metadata without creating files,
loading the model or authorizing a write. It remains usable with broken project
configuration. A status observation is neither a reservation nor an unlock.

`recover_project_lock` retains explicit force, actor/reason, expected hash,
native mutex and owner/risk checks for compatibility. It never removes an owner
record, writes a recovery audit or grants a writer lock. Even a proved dead
owner with explicit risk acknowledgement ends in refusal. It cannot bypass an
active mutex, changed root/owner, journal or unknown safety condition.

The original receipt/journal codecs still validate immutable historical data.
They do not supply repair authority. Behavior tests retain real competing
processes, forked handles, stale/unknown owners, changed records and native
path protections; old successful-unlock oracles now require preserved bytes
and refusal. All execution belongs to the individual Apply gate.
