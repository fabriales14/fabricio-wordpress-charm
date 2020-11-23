#!/usr/bin/env python3

import sys
sys.path.append('lib') 

"""libraries needed for charm."""
from ops.charm import CharmBase, CharmEvents
from ops.framework import EventSource, EventBase, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus

import logging
import yaml
import subprocess

logger = logging.getLogger(__name__)

class WordPressReadyEvent(EventBase):
    pass

class WordPressCharmEvents(CharmEvents):
    wordpress_ready = EventSource(WordPressReadyEvent)


class WordpressCharm(CharmBase):
    on = WordPressCharmEvents()
    state = StoredState()

    def __init__(self, parent, key):
        super().__init__(parent, key)

        self.framework.observe(self.on.start, self)
        self.framework.observe(self.on.stop, self)
        self.framework.observe(self.on.config_changed, self)
        self.framework.observe(self.on.db_relation_changed, self)
        self.framework.observe(self.on.leader_elected, self)
        self.framework.observe(self.on.wordpress_ready, self)
        self.state.set_default(spec=None)

    def on_start(self, event):
        logger.info('Ran on_start')
        new_pod_spec = self.make_pod_spec()
        self._apply_spec(new_pod_spec)

    def on_stop(self, event):
        logger.info('Ran on_stop')

    def on_config_changed(self, event):
        logger.info('Ran on_config_changed')
        new_spec = self.make_pod_spec()

        if self.state.spec != new_spec:
            self._apply_spec(new_spec)

        self.framework.model.unit.status = ActiveStatus()

    def on_db_relation_changed(self, event):
        if not self.state.ready:
            event.defer()
            return

    def on_leader_elected(self, event):
        logger.info('Ran on_leader_elected')

    def on_wordpress_ready(self, event):
        pass

    def on_update_status(self, event):
        logger.info('Ran on_update_status')
        new_pod_spec = self.make_pod_spec()
        self._apply_spec(new_pod_spec)

    def _apply_spec(self, spec):
        # Only apply the spec if this unit is a leader.
        if self.framework.model.unit.is_leader():
            logger.info('{} unit is a leader - applying spec'.format(self.unit))
            self.framework.model.pod.set_spec(spec)
            self.state.spec = spec

    def make_pod_spec(self):
        # accessing config yaml file 
        config = self.framework.model.config

        container_config = self.sanitized_container_config()
        if container_config is None:
            return  # status already set

        # container ports configuration
        ports = [{"name": "http", "containerPort": 80, "protocol": "TCP"}]

        spec = {
            "containers": [
                {"name": self.framework.model.app.name, "image": config["image"], "ports": ports, "config": container_config}
            ]
        }

        # Add the secrets after logging
        config_with_secrets = self.full_container_config()
        if config_with_secrets is None:
            return None

        container_config.update(config_with_secrets)

        return spec

    def sanitized_container_config(self):
        """Uninterpolated container config without secrets"""
        config = self.framework.model.config

        if config["container_config"].strip() == "":
            container_config = {}
        else:
            container_config = yaml.safe_load(self.framework.model.config["container_config"])
            if not isinstance(container_config, dict):
                self.framework.model.unit.status = BlockedStatus("container_config is not a YAML mapping")
                return None
        return container_config

    def full_container_config(self):
        """Uninterpolated container config with secrets"""
        config = self.framework.model.config
        container_config = self.sanitized_container_config()
        if container_config is None:
            return None
        if config["container_secrets"].strip() == "":
            container_secrets = {}
        else:
            container_secrets = yaml.safe_load(config["container_secrets"])
            if not isinstance(container_secrets, dict):
                self.framework.model.unit.status = BlockedStatus("container_secrets is not a YAML mapping")
                return None
        container_config.update(container_secrets)
        return container_config


if __name__ == '__main__':
    main(WordpressCharm)