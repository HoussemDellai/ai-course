resource "azurerm_machine_learning_compute_instance" "aml_compute_instance" {
  name                          = "aml-compute-instance"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.aml_workspace.id
  virtual_machine_size          = "Standard_DS2_v2"
  authorization_type            = "personal"
  subnet_resource_id            = azurerm_subnet.snet_aml_compute.id
  description                   = "foo"

  ssh {
    public_key = var.ssh_key
  }
}

variable "ssh_key" {
  default = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCqaZoyiz1qbdOQ8xEf6uEu1cCwYowo5FHtsBhqLoDnnp7KUTEBN+L2NxRIfQ781rxV6Iq5jSav6b2Q8z5KiseOlvKA/RF2wqU0UPYqQviQhLmW6THTpmrv/YkUCuzxDpsH7DUDhZcwySLKVVe0Qm3+5N2Ta6UYH3lsDf9R9wTP2K/+vAnflKebuypNlmocIvakFWoZda18FOmsOoIVXQ8HWFNCuw9ZCunMSN62QGamCe3dL5cXlkgHYv7ekJE15IA9aOJcM7e90oeTqo+7HTcWfdu0qQqPWY5ujyMw/llas8tsXY85LFqRnr3gJ02bAscjc477+X+j/gkpFoN1QEmt terraform@demo.tld"
}
