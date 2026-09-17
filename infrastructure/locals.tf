locals {
  effective_scan_regions = (
    var.scan_regions != null
    ? distinct(var.scan_regions)
    : [var.aws_region]
  )
}