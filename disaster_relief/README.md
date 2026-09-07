# Disaster Relief Resource Management

`disaster_relief` is an Odoo 19 application for coordinating disaster incidents,
affected areas, relief camps, resource inventory, emergency requests, deliveries,
and volunteer teams.

## Installation

1. Copy this directory into an Odoo addons path.
2. Restart Odoo and update the Apps list.
3. Install **Disaster Relief Resource Management**.
4. Assign users to **Disaster Relief User** or **Disaster Relief Manager**.

Demo data is loaded when the database is created with demo data enabled. The
module depends only on `base`; it deliberately does not require Odoo Inventory.

## Typical workflow

Create and activate an incident, then add affected areas, camps, resources, and
volunteer teams. Create an emergency request with one or more resource lines:

`Requested → Under Review → Approved → Resources Allocated → Dispatched → Delivered`

Rejected requests release any reservations. Allocating a request locks each
resource row and reserves stock in the same transaction. Delivery consumes the
reservation and on-hand quantity. If any requested line cannot be reserved, the
transaction fails without leaving partial reservations.

The Dashboard shows incident cards and open request counts. Request Analytics
provides graph and pivot reporting by incident and workflow state.

## Notes and limitations

- This is a lightweight operational inventory layer, not a replacement for
  Odoo's stock valuation, lots, serial numbers, or warehouse routes.
- Delivery completion is currently all-or-nothing for a request. Partial
  shipments can be modelled as separate requests until a shipment-line model
  is needed.
- Users with write access to resources can adjust on-hand quantities; normal
  allocations and releases are guarded by row locks and validation checks.
