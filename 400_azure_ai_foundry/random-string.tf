resource "random_string" "random" {
  length      = 3
  min_numeric = 3
  lower       = true
  upper       = false
  special     = false
}
