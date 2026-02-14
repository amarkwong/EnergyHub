variable "enabled" {
  type    = bool
  default = false
}

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "hosted_zone_id" {
  type    = string
  default = ""
}

variable "acm_certificate_arn" {
  type    = string
  default = ""
}
