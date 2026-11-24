export default function Landscape() {
  return (
    <div className="landscape" aria-hidden="true">
      <div className="landscape__sun" />
      <div className="landscape__haze landscape__haze--one" />
      <div className="landscape__haze landscape__haze--two" />
      <svg className="landscape__art" viewBox="0 0 1600 700" preserveAspectRatio="xMidYMax slice">
        <defs>
          <linearGradient id="hill-back" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#406D4E" />
            <stop offset="1" stopColor="#173D30" />
          </linearGradient>
          <linearGradient id="hill-front" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#244E3A" />
            <stop offset="1" stopColor="#0A2B23" />
          </linearGradient>
          <linearGradient id="building" x1="0" x2="1">
            <stop stopColor="#73977A" />
            <stop offset="1" stopColor="#416B54" />
          </linearGradient>
        </defs>
        <path d="M0 410 190 265l154 111 195-202 201 231 167-177 250 170 171-128 272 174v256H0Z" fill="#557458" opacity=".46" />
        <path d="M0 476c189-87 329-83 488-13 171 76 291 20 430-39 212-89 436-25 682 89v187H0Z" fill="url(#hill-back)" />
        <g opacity=".82">
          <path d="M690 335h106v176H690zM806 292h131v223H806zM949 359h97v164h-97zM1061 311h129v221h-129zM1204 364h90v172h-90z" fill="url(#building)" />
          <path d="M690 335h106l-12-13H704zM806 292h131l-14-14H821zM949 359h97l-11-12h-75zM1061 311h129l-13-14h-102zM1204 364h90l-10-12h-69z" fill="#9CBF91" />
          <path d="M704 346h12v17h-12zm25 0h12v17h-12zm25 0h12v17h-12zm-50 37h12v17h-12zm25 0h12v17h-12zm25 0h12v17h-12zM823 307h14v18h-14zm29 0h14v18h-14zm29 0h14v18h-14zm-58 39h14v18h-14zm29 0h14v18h-14zm29 0h14v18h-14zm-29 40h14v18h-14zm29 0h14v18h-14zM967 371h12v17h-12zm25 0h12v17h-12zm-25 36h12v17h-12zm25 0h12v17h-12zM1077 325h15v19h-15zm30 0h15v19h-15zm30 0h15v19h-15zm-60 39h15v19h-15zm30 0h15v19h-15zm30 0h15v19h-15zm-30 40h15v19h-15zm30 0h15v19h-15zM1218 377h12v17h-12zm25 0h12v17h-12zm-25 36h12v17h-12zm25 0h12v17h-12z" fill="#C5D6A3" opacity=".7" />
        </g>
        <path d="M0 537c155-64 305-71 461-16 163 58 287 98 466 29 214-83 410-103 673-23v173H0Z" fill="url(#hill-front)" />
        <g fill="#183E2E">
          <path d="M141 558h12v76h-12z" /><circle cx="147" cy="545" r="35" /><circle cx="124" cy="558" r="23" /><circle cx="169" cy="561" r="26" />
          <path d="M363 567h11v71h-11z" /><circle cx="369" cy="550" r="30" /><circle cx="348" cy="560" r="22" /><circle cx="390" cy="559" r="22" />
          <path d="M1376 566h13v88h-13z" /><circle cx="1382" cy="548" r="39" /><circle cx="1353" cy="563" r="28" /><circle cx="1412" cy="566" r="26" />
          <path d="M1517 568h11v77h-11z" /><circle cx="1522" cy="550" r="33" /><circle cx="1497" cy="563" r="23" /><circle cx="1544" cy="563" r="23" />
        </g>
        <g fill="#83B87C" opacity=".72">
          <circle cx="95" cy="584" r="4" /><circle cx="245" cy="617" r="5" /><circle cx="293" cy="590" r="3" />
          <circle cx="1303" cy="600" r="4" /><circle cx="1457" cy="617" r="5" /><circle cx="1156" cy="586" r="3" />
        </g>
      </svg>
      <div className="landscape__shade" />
    </div>
  )
}
