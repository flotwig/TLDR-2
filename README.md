# TLDR 2 - A Continuously Updated Historical TLD Records Archive
This repository is updated hourly with the results from [DNS zone transfer attempts](https://en.wikipedia.org/wiki/DNS_zone_transfer) against the [root nameservers](https://en.wikipedia.org/wiki/Root_name_server) and all existing TLD servers. This is done to keep record of zone files for various TLDs and to monitor how these zones change overtime.

[Click here to view the list of commits and see how the various TLD & root zones change overtime.](https://github.com/flotwig/TLDR-2/commits/main)

[Click here to view the list of nameservers with zone transfers enabled.](https://github.com/flotwig/TLDR-2/blob/main/transferable_zones.md)

## Zone Transfers for Roots and TLDs
Allowing global zone transfers is sometimes considered a security vulnerability due to this functionality giving attackers the ability to easily enumerate all DNS zone data for a specific domain. This is often seen as an issue for system administrators who want to make enumeration of sub-domains and other DNS data hard for malicious actors.

However, when it comes to TLDs and the root nameservers, zone transfers are shown in a different light. Zone transfers at this level can be beneficial as they are an easy way for a TLD to be transparent about its DNS changes. This project is **not** meant to encourage TLD DNS hosting providers to disable global zone transfers but rather to gather data on the ever-changing zone information for the Internet's TLDs.

## Fork Info
This is a fork of the original (discontinued) TLDR project by Matthew Bryant, which can be found here: https://github.com/mandatoryprogrammer/TLDR

Differences between TLDR-2 and TLDR:
* TLDR-2 will request up to 25 simultaneous AXFRs, TLDR will only request 1. This significantly boosts the speed of a full scan.
* TLDR-2 only saves successful AXFRs. This should help keep the repo a manageable size and make the results easier to navigate.
* TLDR-2 is actively updated, using a GitHub Action to keep up to date.
* In addition to `transferable_zones.md`, TLDR-2 generates a tab-separated list of AXFR-able zones in `transferable_zones.tsv`.

## Credit
This project was inspired by Peter Bowen's work which can be found here: https://github.com/pzb/TLDs

## See Also

* [`zone-walks`](https://github.com/flotwig/zone-walks) - a collection of domains collected from DNSSEC zone-walking TLDs. Auto-updated.
