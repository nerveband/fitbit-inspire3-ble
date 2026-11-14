// Passive BLE scan from the Mac's own adapter, to see how the tracker advertises.
// Build: swiftc -O blescan.swift -o blescan
// Run:   ./blescan 12
import Foundation
import CoreBluetooth

final class Scanner: NSObject, CBCentralManagerDelegate {
    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral, advertisementData d: [String: Any], rssi RSSI: NSNumber) {
        onDiscover(c, p, d, RSSI.intValue)
    }
    var central: CBCentralManager!
    var seen: [UUID: (name: String, rssi: Int, services: [String], mfg: String?)] = [:]
    let deadline: Date

    init(seconds: Double) {
        deadline = Date().addingTimeInterval(seconds)
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        print("adapter state: \(c.state.rawValue) (5 = powered on)")
        if c.state == .poweredOn {
            print("scanning...")
            c.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        }
    }

    func onDiscover(_ c: CBCentralManager, _ p: CBPeripheral, _ d: [String: Any], _ rssi: Int) {
        let name = (d[CBAdvertisementDataLocalNameKey] as? String) ?? p.name ?? ""
        var svcs: [String] = []
        if let u = d[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] { svcs = u.map { $0.uuidString } }
        var mfg = "-"
        if let m = d[CBAdvertisementDataManufacturerDataKey] as? Data {
            mfg = m.map { String(format: "%02x", $0) }.joined()
        }
        seen[p.identifier] = (name, rssi, svcs, mfg)
    }

    func report() {
        print("\n--- peripherals seen: \(seen.count) ---")
        let rows = seen.sorted { $0.value.rssi > $1.value.rssi }
        for (id, v) in rows {
            print(String(format: "%-22s rssi=%4d  svc=%@  mfg=%@  id=%@",
                         (v.name as NSString).utf8String!, v.rssi,
                         v.services.joined(separator: ",") as NSString,
                         String((v.mfg ?? "-").prefix(30)) as NSString,
                         id.uuidString as NSString))
        }
        print("\n--- unnamed/uninteresting: \(seen.filter { $0.value.name.isEmpty && $0.value.services.isEmpty }.count) ---")
    }
}

let secs = CommandLine.arguments.count > 1 ? Double(CommandLine.arguments[1])! : 10.0
let s = Scanner(seconds: secs)
RunLoop.current.run(until: Date().addingTimeInterval(secs))
s.central.stopScan()
s.report()
