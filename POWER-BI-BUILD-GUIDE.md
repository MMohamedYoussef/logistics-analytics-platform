# Power BI report design

Import `artifacts/powerbi_shipments.csv` as table **Shipments**. Confirm that `order_date`, `promised_date` and `delivered_date` are Date; `shipping_cost_usd` is Decimal Number; `on_time` and `returned` are True/False. Set `shipment_id` to Text and do not summarize it.

Create these measures:

```DAX
Shipments = COUNTROWS(Shipments)
On-Time Deliveries = CALCULATE([Shipments], Shipments[on_time] = TRUE())
On-Time % = DIVIDE([On-Time Deliveries], [Shipments])
Shipping Cost = SUM(Shipments[shipping_cost_usd])
Returns = CALCULATE([Shipments], Shipments[returned] = TRUE())
Return Rate = DIVIDE([Returns], [Shipments])
```

Format `On-Time %` and `Return Rate` as Percentage, `Shipping Cost` as Currency (USD). Create an **Executive** page with cards for the four primary metrics, horizontal bars of On-Time % by `region`, and Shipping Cost by `carrier`. Add slicers for `order_date`, `region` and `carrier`. Create a **Delivery Detail** page with a table of shipment ID, dates, region, carrier, on-time flag, cost and return flag. Use a dark navy background with teal for on-time values and rose for late/returned values. The PNG in `assets/` is a static design preview generated from the same CSV; it is not a Power BI workbook.

Reconcile the unfiltered report against `artifacts/summary.json`: Shipments 600, Shipping Cost $14,180.77, On-Time 55.67%, Returns 40 for the checked-in seed. Refresh after regenerating the CSV.
