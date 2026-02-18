import { useEffect, useMemo, useState } from "react";

type EntityLogoProps = {
  name: string;
  type: "retailer" | "network";
  className?: string;
};

const logoDomainByRetailer: Record<string, string> = {
  agl: "agl.com.au",
  "origin energy": "originenergy.com.au",
  energyaustralia: "energyaustralia.com.au",
  "alinta energy": "alintaenergy.com.au",
  "red energy": "redenergy.com.au",
  engie: "engie.com.au",
  "1st energy": "1stenergy.com.au",
  powershop: "powershop.com.au",
  dodo: "dodo.com",
  actewagl: "actewagl.com.au",
  lumo: "lumoenergy.com.au",
  "momentum energy": "momentumenergy.com.au",
  bluenrg: "bluenrg.com.au",
  "ovo energy": "ovoenergy.com.au",
  "arcline by racv": "racv.com.au",
};

const logoDomainByNetwork: Record<string, string> = {
  ausgrid: "ausgrid.com.au",
  endeavour_energy: "endeavourenergy.com.au",
  essential_energy: "essentialenergy.com.au",
  energex: "energex.com.au",
  ergon_energy: "ergon.com.au",
  ausnet_services: "ausnetservices.com.au",
  citipower: "citipower.com.au",
  jemena: "jemena.com.au",
  powercor: "powercor.com.au",
  united_energy: "unitedenergy.com.au",
  evoenergy: "evoenergy.com.au",
  tasnetworks: "tasnetworks.com.au",
};

const officialLogoByRetailer: Record<string, string> = {
  agl: "https://www.agl.com.au/content/dam/aglweb/images/agl-jtc-logo.svg",
  "origin energy": "",
  energyaustralia:
    "https://www.energyaustralia.com.au/themes/custom/ea/assets/images/EA_logo.svg",
  "alinta energy":
    "https://www.alintaenergy.com.au/content/experience-fragments/alinta/global/footer/master/_jcr_content/root/container/columncontrol/columncontrolcontainer/image.coreimg.svg/1741829867656/alintalogo.svg",
  "red energy": "https://www.redenergy.com.au/assets/img/logo-red-energy.png",
  engie:
    "https://engie.com.au/themes/custom/sunrise/images/engie-blue.f6c6ec1f.svg",
  "1st energy": "",
  powershop: "",
  dodo: "",
  actewagl: "",
  lumo: "",
  "momentum energy": "",
  bluenrg: "",
  "ovo energy": "",
  "arcline by racv": "",
};

const officialLogoByNetwork: Record<string, string> = {
  ausgrid: "",
  endeavour_energy: "https://www.endeavourenergy.com.au/images/ee-logo.svg",
  essential_energy:
    "https://www.essentialenergy.com.au/-/media/Project/EssentialEnergy/shared/logo.svg?h=80&hash=D6C3FD15E19E68C6E18B41E553560CAF&iar=0&rev=925606df76504085aff1409a92286cf5&w=157",
  energex: "https://upload.wikimedia.org/wikipedia/en/3/38/Energex_logo.png",
  ergon_energy:
    "https://upload.wikimedia.org/wikipedia/en/c/c0/Ergon_aus_logo.jpg",
  ausnet_services:
    "https://www.ausnetservices.com.au/-/media/project/ausnet/corporate-website/components/header/ausnet-logo.svg?hash=0BD369FBA0DACEA8198262AD212B284B&iar=0&rev=cf580f366ffc4e2a8d736f1a3525e456",
  citipower:
    "https://www.citipower.com.au/static/logo-d99693e8c3c9ff162aa712e322de6b26.svg",
  jemena:
    "https://www.jemena.com.au/globalassets/images/logos/jemena-logo-horizontal.png",
  powercor:
    "https://www.powercor.com.au/static/logo-d99693e8c3c9ff162aa712e322de6b26.svg",
  united_energy:
    "https://www.unitedenergy.com.au/static/c50341b110a35486f15e1fd4f5e418d5/8b28a/ue-logo.png",
  evoenergy:
    "https://www.evoenergy.com.au/-/media/Project/Evoenergy/EVO/Header/logo-evo.svg",
  tasnetworks:
    "https://upload.wikimedia.org/wikipedia/en/thumb/b/b4/Logo_TasNetworks.png/250px-Logo_TasNetworks.png",
};

const localLogoByRetailer: Record<string, string> = {
  agl: "/logos/retailers/agl.svg",
  "origin energy": "/logos/retailers/origin-energy.svg",
  energyaustralia: "/logos/retailers/energyaustralia.svg",
  "alinta energy": "/logos/retailers/alinta-energy.svg",
  "red energy": "/logos/retailers/red-energy.png",
  engie: "/logos/retailers/engie.svg",
  "1st energy": "/logos/retailers/1st-energy.svg",
  powershop: "/logos/retailers/powershop.svg",
  dodo: "/logos/retailers/dodo.svg",
  actewagl: "/logos/retailers/actewagl.svg",
  lumo: "/logos/retailers/lumo.svg",
  "momentum energy": "/logos/retailers/momentum-energy.svg",
  bluenrg: "/logos/retailers/bluenrg.svg",
  "ovo energy": "/logos/retailers/ovo-energy.svg",
  "arcline by racv": "/logos/retailers/arcline-by-racv.svg",
};

const localLogoByNetwork: Record<string, string> = {
  ausgrid: "/logos/network/ausgrid.svg",
  endeavour_energy: "/logos/network/endeavour-energy.svg",
  essential_energy: "/logos/network/essential-energy.svg",
  energex: "/logos/network/energex.svg",
  ergon_energy: "/logos/network/ergon-energy.svg",
  ausnet_services: "/logos/network/ausnet-services.svg",
  citipower: "/logos/network/citipower.svg",
  jemena: "/logos/network/jemena.svg",
  powercor: "/logos/network/powercor.svg",
  united_energy: "/logos/network/united-energy.svg",
  evoenergy: "/logos/network/evoenergy.svg",
  tasnetworks: "/logos/network/tasnetworks.svg",
};

function toKey(name: string) {
  return name.trim().toLowerCase().replace(/\s+/g, " ");
}

function initials(name: string) {
  return name
    .split(/[\s_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

export default function EntityLogo({
  name,
  type,
  className = "",
}: EntityLogoProps) {
  const [sourceIndex, setSourceIndex] = useState(0);
  useEffect(() => {
    setSourceIndex(0);
  }, [name, type]);

  const domain = useMemo(() => {
    if (type === "retailer") {
      return logoDomainByRetailer[toKey(name)];
    }
    return logoDomainByNetwork[name] || logoDomainByNetwork[toKey(name)];
  }, [name, type]);

  const official = useMemo(() => {
    const key = toKey(name);
    if (type === "retailer") return officialLogoByRetailer[key] || "";
    return officialLogoByNetwork[name] || officialLogoByNetwork[key] || "";
  }, [name, type]);

  const local = useMemo(() => {
    const key = toKey(name);
    if (type === "retailer") return localLogoByRetailer[key] || "";
    return localLogoByNetwork[name] || localLogoByNetwork[key] || "";
  }, [name, type]);

  const sources = useMemo(() => {
    const resolved = [
      local,
      official,
      domain ? `https://logo.clearbit.com/${domain}` : "",
    ].filter(Boolean);
    return Array.from(new Set(resolved));
  }, [local, official, domain]);
  const src = sources[sourceIndex] ?? null;
  const fallbackText = initials(name);

  if (!src) {
    return (
      <div
        className={`inline-flex h-9 w-9 items-center justify-center rounded-md bg-slate-200 text-xs font-semibold text-slate-700 ${className}`}
        title={name}
      >
        {fallbackText}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={`${name} logo`}
      className={`h-9 w-9 object-contain ${className}`}
      onError={() => setSourceIndex((idx) => idx + 1)}
      loading="lazy"
      referrerPolicy="no-referrer"
    />
  );
}
