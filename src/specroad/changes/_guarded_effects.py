"""One bound file effect; the guard session owns authorization and completion."""
from hashlib import sha256
import os
from ..security import paths as guards
from ._publication_io import replace_bound_image
from ._publication_observation import _stamp
from .publication_check import _rights
from .write_guard_values import require, WriteGuardError


def make_parents(self,path):
    parts=tuple(path.split('/')[:-1])
    for index in range(1,len(parts)+1):
        key=parts[:index]
        if self.parents[key] is not None:continue
        self.guard()
        with self.files.directory(key[:-1]) as parent:
            require(parent is not None,'write_parent_missing')
            _rights(parent,path);os.mkdir(key[-1],mode=0o700,dir_fd=parent)
            self.parents[key]=_stamp(os.stat(key[-1],dir_fd=parent,follow_symlinks=False));os.fsync(parent)
        self.guard()

def publish_effect(self,index,path):
    self.guard();make_parents(self,path);self.guard()
    before=self.before.get(path);after=self.target.get(path)
    require(not path.startswith('archive/objects/') or before is None,'immutable_write_target',exit_code=7)
    with self.files.directory(tuple(path.split('/')[:-1])) as fd:
        require(fd is not None,'write_parent_missing');_rights(fd,path)
        name=path.rsplit('/',1)[-1]
        if after is None:
            require(before is not None,'write_delete_without_source')
            self.guard();os.unlink(name,dir_fd=fd)
            self.expected.pop(path);self.identities.pop(path);self.modes.pop(path);self.owners.pop(path)
            self.checkpoint('effect_unlinked:'+str(index));os.fsync(fd)
        else:
            staged=str(index)+'.bin';raw,ident=self.images[staged]
            def moved(info):
                self.expected[path]=after;self.identities[path]=guards._identity(info)
                self.modes[path]=info.st_mode&0o777;self.owners[path]=(info.st_uid,info.st_gid);self.images.pop(staged)
                self.checkpoint('effect_replaced:'+str(index))
            with self.files.directory(('.specroad','write-state','staging')) as stage:
                replace_bound_image(stage,staged,fd,name,size=len(raw),digest=sha256(raw).hexdigest(),identity=ident,
                    mode=self.modes.get(path,0o644),create_only=before is None,single_link_create=True,
                    source_changed=lambda:WriteGuardError('write_image_changed',exit_code=6),
                    before_replace=self.guard,after_replace=moved)
    self.guard();self.checkpoint('effect_synced:'+str(index));self.guard()
