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
test. The selected W gate includes the new lock tests plus the two directly
changed read-only-validation test files; it does not execute a full suite.
