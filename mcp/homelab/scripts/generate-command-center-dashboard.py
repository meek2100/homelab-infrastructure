#!/usr/bin/env python3
"""
Generate Master Homelab Command & Control Center Dashboard JSON for Grafana.
Aggregates Executive Vitals, External Systems (theurer.dev), Physical Network,
Proxmox Hypervisors, In-Guest VM Performance, Full Container Fleet, and Loki Logs.
"""

import json
import os

DASHBOARD_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "infrastructure", "docker-stacks", "nexus-server", "71-monitoring",
        "grafana", "provisioning", "dashboards", "homelab-command-center.json"
    )
)

def create_dashboard():
    panels = []
    panel_id = 1
    y_pos = 0

    # -------------------------------------------------------------
    # Row 1: Executive Vitals & Homelab Overview
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "⚡ Homelab Executive Vitals & Fleet Health",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # Total Scrape Targets UP
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 45}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Active Targets",
        "type": "stat",
        "targets": [{"expr": "sum(up)", "legendFormat": "Targets UP"}]
    })
    panel_id += 1

    # Active Monitored Containers
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "blue", "value": None}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 4, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Active Containers",
        "type": "stat",
        "targets": [{"expr": "count(count by (name) (container_last_seen{name=~\".+\"}))", "legendFormat": "Containers"}]
    })
    panel_id += 1

    # Active Alerts Firing
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 8, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Active Alerts",
        "type": "stat",
        "targets": [{"expr": "sum(alertmanager_alerts{state=\"active\"}) or vector(0)", "legendFormat": "Alerts Firing"}]
    })
    panel_id += 1

    # Proxmox Nodes Online
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 3}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 12, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Hypervisors",
        "type": "stat",
        "targets": [{"expr": "sum(pve_up{id=~\"node/.*\"})", "legendFormat": "Nodes Online"}]
    })
    panel_id += 1

    # Router WAN Bandwidth
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "bps",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 4, "w": 8, "x": 16, "y": y_pos},
        "id": panel_id,
        "title": "Router WAN Real-Time Bandwidth",
        "type": "timeseries",
        "targets": [
            {"expr": "rate(ifInOctets{job=\"snmp_infrastructure\", instance=\"192.168.1.1\", ifDescr=\"eth0\"}[1m]) * 8", "legendFormat": "WAN Download"},
            {"expr": "rate(ifOutOctets{job=\"snmp_infrastructure\", instance=\"192.168.1.1\", ifDescr=\"eth0\"}[1m]) * 8", "legendFormat": "WAN Upload"}
        ]
    })
    panel_id += 1
    y_pos += 4

    # -------------------------------------------------------------
    # Row 2: External Systems (theurer.dev & mail.theurer.dev)
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "🌐 External Systems & Email Infrastructure (theurer.dev)",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # theurer.dev Web HTTP
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [{"options": {"0": {"color": "red", "text": "DOWN"}, "1": {"color": "green", "text": "UP (200 OK)"}}, "type": "value"}],
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "theurer.dev Web",
        "type": "stat",
        "targets": [{"expr": "probe_success{instance=\"https://theurer.dev\", job=\"blackbox_http\"}", "legendFormat": "Web Status"}]
    })
    panel_id += 1

    # theurer.dev SSL Expiry
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "d",
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "yellow", "value": 14}, {"color": "green", "value": 30}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 4, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "theurer.dev SSL Expiry",
        "type": "stat",
        "targets": [{"expr": "(probe_ssl_earliest_cert_expiry{instance=\"https://theurer.dev\"} - time()) / 86400", "legendFormat": "Days Remaining"}]
    })
    panel_id += 1

    # mail.theurer.dev Webmail HTTP
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [{"options": {"0": {"color": "red", "text": "DOWN"}, "1": {"color": "green", "text": "UP (200 OK)"}}, "type": "value"}],
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 8, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "mail.theurer.dev Webmail",
        "type": "stat",
        "targets": [{"expr": "probe_success{instance=\"https://mail.theurer.dev\", job=\"blackbox_http\"}", "legendFormat": "Webmail Status"}]
    })
    panel_id += 1

    # mail.theurer.dev SMTP Submission (:587)
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [{"options": {"0": {"color": "red", "text": "CLOSED"}, "1": {"color": "green", "text": "OPEN (:587)"}}, "type": "value"}],
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 12, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "SMTP Submission (:587)",
        "type": "stat",
        "targets": [{"expr": "probe_success{instance=\"mail.theurer.dev:587\", job=\"blackbox_tcp\"}", "legendFormat": "SMTP :587"}]
    })
    panel_id += 1

    # mail.theurer.dev IMAPS (:993)
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [{"options": {"0": {"color": "red", "text": "CLOSED"}, "1": {"color": "green", "text": "OPEN (:993)"}}, "type": "value"}],
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 16, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "IMAPS Mail Retrieval (:993)",
        "type": "stat",
        "targets": [{"expr": "probe_success{instance=\"mail.theurer.dev:993\", job=\"blackbox_tcp\"}", "legendFormat": "IMAPS :993"}]
    })
    panel_id += 1

    # mail.theurer.dev SSL Expiry
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "d",
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "yellow", "value": 14}, {"color": "green", "value": 30}]}
            }
        },
        "gridPos": {"h": 4, "w": 4, "x": 20, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Mail SSL Expiry",
        "type": "stat",
        "targets": [{"expr": "(probe_ssl_earliest_cert_expiry{instance=\"https://mail.theurer.dev\"} - time()) / 86400", "legendFormat": "Days Remaining"}]
    })
    panel_id += 1
    y_pos += 4

    # -------------------------------------------------------------
    # Row 3: Physical Network & Distribution
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "🔌 Physical Network, Switch Ports & AP Fleet",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # Switch Top Active Port Bandwidth
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "bps",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 6, "w": 16, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "Araknis 920 Switch Active Port Throughput (Top Ports)",
        "type": "timeseries",
        "targets": [
            {"expr": "topk(6, rate(ifInOctets{job=\"snmp_infrastructure\", instance=\"192.168.1.215\", ifIndex=~\"1|2|3|4|5|6|7|8|25|26\"}[1m]) * 8)", "legendFormat": "{{ifDescr}} (Rx)"}
        ]
    })
    panel_id += 1

    # Printer Toner Levels
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "percent",
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "yellow", "value": 15}, {"color": "green", "value": 30}]}
            }
        },
        "gridPos": {"h": 6, "w": 8, "x": 16, "y": y_pos},
        "id": panel_id,
        "options": {"orientation": "horizontal", "showThresholdLabels": False, "showThresholdMarkers": True},
        "title": "HP LaserJet M283cdw Toner Supplies",
        "type": "gauge",
        "targets": [
            {"expr": "(prtMarkerSuppliesLevel{job=\"snmp_printers\", instance=\"192.168.10.195\"} / prtMarkerSuppliesMaxCapacity{job=\"snmp_printers\", instance=\"192.168.10.195\"}) * 100", "legendFormat": "{{prtMarkerSuppliesDescription}}"}
        ]
    })
    panel_id += 1
    y_pos += 6

    # -------------------------------------------------------------
    # Row 4: Fleet Virtual Machines & In-Guest Performance
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "💻 Proxmox Hypervisors & In-Guest Fleet VM Performance",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # VM CPU Utilization
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "percent",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 6, "w": 12, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "Fleet In-Guest CPU Utilization (%)",
        "type": "timeseries",
        "targets": [
            {"expr": "100 - (avg by (instance_name) (rate(node_cpu_seconds_total{mode=\"idle\"}[1m])) * 100)", "legendFormat": "{{instance_name}}"}
        ]
    })
    panel_id += 1

    # VM Memory Consumption
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "bytes",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 6, "w": 12, "x": 12, "y": y_pos},
        "id": panel_id,
        "title": "Fleet In-Guest Memory Consumption",
        "type": "timeseries",
        "targets": [
            {"expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "legendFormat": "{{instance_name}} Used RAM"}
        ]
    })
    panel_id += 1
    y_pos += 6

    # -------------------------------------------------------------
    # Row 5: Docker Container Fleet Telemetry (cAdvisor)
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "🐳 Docker Container Fleet Performance (cAdvisor Telemetry across all VMs)",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # Top Containers by Memory
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "bytes",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 6, "w": 12, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "Top 8 Containers by Memory Consumption",
        "type": "timeseries",
        "targets": [
            {"expr": "topk(8, container_memory_working_set_bytes{name=~\".+\"})", "legendFormat": "{{name}}"}
        ]
    })
    panel_id += 1

    # Top Containers by CPU
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "unit": "percent",
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth"}
            }
        },
        "gridPos": {"h": 6, "w": 12, "x": 12, "y": y_pos},
        "id": panel_id,
        "title": "Top 8 Containers by CPU Utilization (%)",
        "type": "timeseries",
        "targets": [
            {"expr": "topk(8, rate(container_cpu_usage_seconds_total{name=~\".+\"}[1m]) * 100)", "legendFormat": "{{name}}"}
        ]
    })
    panel_id += 1
    y_pos += 6

    # -------------------------------------------------------------
    # Row 5: Application Health & Web Port Matrix
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "📱 Application Web Services & API Health Matrix",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # Status Grid for Web Services
    panels.append({
        "datasource": {"type": "prometheus", "uid": "Prometheus"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [
                    {"options": {"0": {"color": "red", "text": "DOWN"}, "1": {"color": "green", "text": "HEALTHY"}}, "type": "value"}
                ],
                "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
            }
        },
        "gridPos": {"h": 6, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "title": "Homelab Core Web Applications Status (Blackbox Probes)",
        "type": "stat",
        "targets": [
            {"expr": "probe_success{job=\"blackbox_http\"}", "legendFormat": "{{service}}"}
        ]
    })
    panel_id += 1
    y_pos += 6

    # -------------------------------------------------------------
    # Row 6: Consolidated Loki Log Stream
    # -------------------------------------------------------------
    panels.append({
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "title": "📜 Consolidated Fleet Log Explorer (Loki 3.0 Real-Time Streams)",
        "type": "row"
    })
    panel_id += 1
    y_pos += 1

    # Live Log Stream
    panels.append({
        "datasource": {"type": "loki", "uid": "Loki"},
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {
            "showLabels": True,
            "wrapLogMessage": True,
            "enableLogDetails": True,
            "sortOrder": "Descending",
            "dedupStrategy": "none"
        },
        "title": "Consolidated Live Log Stream (All VMs & Containers)",
        "type": "logs",
        "targets": [
            {"expr": "{vm=~\".+\"}", "legendFormat": "{{vm}} - {{container}}"}
        ]
    })
    panel_id += 1
    y_pos += 10

    dashboard = {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "panels": panels,
        "refresh": "10s",
        "schemaVersion": 39,
        "tags": ["homelab", "control-center", "network", "proxmox", "docker", "loki", "external"],
        "templating": {"list": []},
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "Homelab Command & Control Center",
        "uid": "homelab-command-center",
        "version": 1,
        "weekStart": ""
    }

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)

    print(f"✅ Generated Master Control Center Dashboard with {len(panels)} panels at:\n{DASHBOARD_FILE}")

if __name__ == "__main__":
    create_dashboard()
