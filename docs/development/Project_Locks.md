# Native project locks (5.i)

`specroad.changes.project_lock` is an explicit process-local context manager for
cooperating native Linux clients. Writer, recovery and operational lock kinds
share an exclusive, nonblocking `flock` on the **project root directory inode**.
There is no removable guard pathname whose replacement could split two mutexes.
Unsupported platforms/filesystems fail closed; this is not a network/distributed
lease or a sandbox against noncooperating writers. Native Pixel/PRoot capability
is established by its actual selected tests, not inferred from the host name.

The operational owner record is `.specroad/locks/project.json`, mode 0600.
It binds a v4 lock UUID, lock kind, logical project identity, local root device and
inode, process ID, process-start token, boot/PID-namespace host observation,
UTC creation time, command, request ID and transaction ID. Unknown host/start
observations remain null, never invented proof. A mutable hostname is not an
ownership identity. Different boots/namespaces are conservatively foreign.

Writer acquisition verifies the existing project configuration and refuses
unresolved transaction/recovery/unknown operational entries. Recovery acquires
the same exclusive mutex without loading the ordinary model; it leaves journals
for the later recovery engine. Old records are never automatically stolen,
including after the owning process has exited. Only the exact owner bytes and
file identity are removed on normal release. Foreign replacements are preserved.
A child cannot release its parent's handle; handles cannot be copied/serialized.

`inspect_project_lock` is read-only, including with broken project configuration.
It does not create directories, take a writer lock, open journal contents or
perform recovery. Status is a rechecked observation, not a reservation and not
write authorization. Empty lock directories left after release do not block the
existing read-only validation path; an actual record still blocks that shallow
reader until its owner is resolved.

No native transaction backend, CLI lock commands, journal parser, implicit
repair, process termination or automatic request receipts are introduced here.
All working data and temporary project roots in the tests are private to the
test. The lock tests and the two related read-only-validation test files contain
the behavioral evidence for this section. Test execution follows the local
`AGENTS.md`; see [Testing.md](Testing.md) for the technical commands.

## Explicit recovery (5.i.R)

`recover_project_lock` requires the exact observed lock-byte SHA-256, project
identity, explicit force, actor and reason. It first obtains the SAME root-inode
mutex. A busy mutex can never be bypassed, including with risk acknowledgement.
Alive same-host process/start observations always refuse removal. Foreign or
unverifiable host/start observations and PID reuse additionally require explicit
`accept_remote_risk=True`. A missing proc record alone does not prove death:
hidepid/permission cases stay unknown unless a nonmutating process existence
probe also proves absence. New hostnames are not an ownership proof.

The library does not remove another machine's actual kernel lock or kill any
process. Risk consent is only about uncertain *orphan metadata* on the local
filesystem; it cannot override an active local kernel holder, bad path, changed
root/owner, or a transaction journal. The probe parameter is a trusted embedded
application adapter, never configured/imported from project files. Actor data is
an audit declaration, not authentication.

An immutable 0600 intent event is written under
`.specroad/recovery/lock-audit/<event-id>.intent.json` **before** removing the
orphan. Owner bytes/inode, start observation and journal presence are rechecked.
Only afterwards is a separate completion event created. Intent never claims
removal. Interrupted audit/removal/completion produces an error with
`mutation_possible=true`; existing events and any remaining owner are preserved.
No automatic retry/rollback rewrites audit history. Recovery does not itself
acquire a new writer lock and does not modify or interpret journals.

Descriptor-relative nofollow I/O rejects symlinks, hardlinked owner records,
special files and nested roots. Root/directory/record changes are rechecked.
This is protection for cooperating local clients with trusted kernel/filesystem
semantics, not an OS compare-and-swap guarantee against a hostile concurrent
filesystem actor. The lock kind is not a privilege or a completed native writer.
The new three-way mutual exclusion and forced-orphan recovery are not yet wired
into every later CLI command or the unimplemented durable transaction backend.

Both lock test files and the related read-only-validation files remain part of
the full suite, without a separate Apply selection. Real competing processes,
abrupt exit, forked handles, active journals, reused PIDs, unknown hosts,
changing records, I/O failures and portable
distributions are tested. There is no artificial test/suite timeout and no test
that compares human-readable output or documentation layout.
