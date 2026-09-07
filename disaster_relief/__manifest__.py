{
    "name": "Disaster Relief Resource Management",
    "summary": "Coordinate incidents, camps, resources, requests, volunteers, and deliveries",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "author": "Disaster Relief Team",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/disaster_relief_views.xml",
        "views/disaster_relief_menus.xml",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "installable": True,
    "application": True,
}
