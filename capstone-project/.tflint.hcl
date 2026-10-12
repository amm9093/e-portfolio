# TFLint configuration (report: "The delivery pipeline and its validation", step 2).
# Uses the bundled Terraform ruleset: unused declarations, missing version
# pins, naming conventions, documented variables and outputs.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
}
