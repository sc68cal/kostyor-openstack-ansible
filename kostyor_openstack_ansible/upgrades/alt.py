# This file is part of OpenStack Ansible driver for Kostyor.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager

from kostyor.rpc import tasks
from kostyor.rpc.app import app

# TODO(sc68cal) figure out if this is actually viable
from kostyor.db import api as dbapi

from . import base


@app.task(bind=True, base=tasks.execute.__class__)
def _run_playbook(self, playbook, cwd=None, ignore_errors=False):
    return super(_run_playbook.__class__, self).run(
        [
            '/usr/local/bin/openstack-ansible', playbook,
        ],
        cwd=cwd,
        ignore_errors=ignore_errors,
    )


@app.task(bind=True, base=tasks.execute.__class__)
def _run_playbook_for(self, playbook, node, service, cwd=None,
                      ignore_errors=False):
    inventory = Inventory(DataLoader(), VariableManager())
    hosts = [
        host.get_vars()['inventory_hostname']
        for host in base.get_component_hosts_on_node(
            inventory, service, node
        )
    ]

    return super(_run_playbook_for.__class__, self).run(
        [
            '/usr/local/bin/openstack-ansible', playbook,
            '-l', ','.join(hosts)
        ],
        cwd=cwd,
        ignore_errors=ignore_errors,
    )


class Driver(base.Driver):

    _run_playbook = _run_playbook
    _run_playbook_for = _run_playbook_for

    def pre_host_upgrade_hook(self, upgrade_task, host):
        # Catch nova-compute upgrades and pass off to a separate handler

        # Figure out if this host has the nova-compute service running
        services_on_host = dbapi.get_services_by_host(host['id'])
        if 'nova-compute' in map(lambda x: x['name'], services_on_host):
            # Step 1 - fence off the compute node
            # i.e. Disable service record in Nova database for the node
            # TODO(sc68cal) Figure out if this needs to be an RPC call back
            # to the Kostyor service
            self.disable_compute_service_record_for_host(host)

            # TODO(sc68cal) Figure out if this needs to be an RPC call back
            # to the Kostyor service
            # Final step - migrate instances off that are on the machine
            self.host_live_evacuate_nova_compute_node(host)
