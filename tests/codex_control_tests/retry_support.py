"""Independent tiny Git fixture; never reconstruct a user repository/history."""
import os
import subprocess
from specroad_control.local import json_write


def git(repository, *args):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    result = subprocess.run(['git','-c','user.name=Control Tests','-c','user.email=tests@example.invalid',
                             '-c','commit.gpgsign=false','-C',str(repository),*args],
                            env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    return result.stdout


def initialize_git(repository):
    git(repository,'init','--quiet')
    (repository/'fixture.txt').write_text('independent fixture\n')
    git(repository,'add','--','fixture.txt')
    git(repository,'commit','--quiet','-m','Independent test fixture')
