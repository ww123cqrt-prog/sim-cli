import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.File;
import java.util.*;

/** Read-only structural verifier. It never runs geometry, mesh, study, or solver. */
public class VerifyBlochModeFollowingBase {
  static void require(boolean value, String message) throws Exception {
    if (!value) throw new Exception("VERIFY_FAILED: " + message);
  }

  static String modelPath() {
    return "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";
  }

  static boolean has(String[] values, String expected) {
    return Arrays.asList(values).contains(expected);
  }

  static Set<Integer> set(int[] values) {
    Set<Integer> out = new TreeSet<>();
    for (int value : values) out.add(value);
    return out;
  }

  static void periodic(Model m, String tag, int axis) throws Exception {
    int[] all = m.component("comp1").physics("ewfd").feature(tag)
        .selection().entities(2);
    int[] destination = m.component("comp1").physics("ewfd").feature(tag)
        .selection("destinationDomains").entities(2);
    Set<Integer> source = set(all);
    source.removeAll(set(destination));
    require(source.size() == 5 && destination.length == 5, tag + " boundary count");
    double sm = 0, dm = 0;
    for (int b : source) sm += coordinate(m, b, axis);
    for (int b : destination) dm += coordinate(m, b, axis);
    double translation = dm / destination.length - sm / source.size();
    require(Math.abs(translation - 1e-6) < 1e-12, tag + " translation");
  }

  static double coordinate(Model m, int boundary, int axis) throws Exception {
    m.component("comp1").geom("geom1").measureFinal().selection().geom(2);
    m.component("comp1").geom("geom1").measureFinal().selection().set(boundary);
    double[] box = m.component("comp1").geom("geom1").measureFinal().getBoundingBox();
    return 0.5 * (box[2 * axis] + box[2 * axis + 1]);
  }

  public static void main(String[] args) throws Exception {
    String path = modelPath();
    Model m = ModelUtil.load("VerifyBlochMF", path);
    require(ModelUtil.getComsolVersion().startsWith("COMSOL Multiphysics 6.4"), "COMSOL version");
    require(m.component("comp1").geom("geom1").getNDomains() == 5, "domain count");
    require(m.component("comp1").geom("geom1").getNBoundaries() == 26, "boundary count");
    require(m.component("comp1").mesh("mesh1").getNumElem() == 864, "mesh element count");
    require(m.param().get("kBx").contains("qx_active"), "kBx expression");
    require(m.param().get("kBy").contains("qy_active"), "kBy expression");

    require(!has(m.component("comp1").pair().tags(), "pairx")
        && !has(m.component("comp1").pair().tags(), "pairy"),
        "unused identity pairs must be absent");
    periodic(m, "pcx", 0);
    periodic(m, "pcy", 1);
    for (String tag : new String[]{"pcx", "pcy"}) {
      require("Floquet".equals(m.component("comp1").physics("ewfd").feature(tag)
          .getString("PeriodicType")), tag + " periodic type");
      String[] k = m.component("comp1").physics("ewfd").feature(tag).getStringArray("kFloquet");
      require(k.length == 3 && "kBx".equals(k[0]) && "kBy".equals(k[1]) && "0".equals(k[2]),
          tag + " full Floquet vector");
      require(m.component("comp1").physics("ewfd").feature(tag)
          .getBoolean("manualDestinationSelection"), tag + " manual destination");
    }

    require(has(m.study().tags(), "std1") && has(m.study().tags(), "stdmf"), "study tags");
    require(has(m.study("stdmf").feature().tags(), "param"),
        "visible Parametric Sweep study step missing");
    require("Parametric".equals(m.study("stdmf").feature("param").getType()),
        "param feature type");
    require("k".equals(m.study("stdmf").feature("param").getString("pname")),
        "swept parameter must be k");
    require(m.study("stdmf").feature("param").getString("plistarr").contains("-0.1"),
        "k sweep start");
    require(m.study("stdmf").feature("param").getString("plistarr").contains("0.1"),
        "k sweep stop");
    require("off".equals(m.study("stdmf").feature("param").getString("pdistrib")),
        "ordered sweep must not distribute points");
    require("on".equals(m.study("stdmf").feature("eig").getString("modefollowing")),
        "study Mode Following");
    require("1".equals(m.param().get("use_k_scan")), "scan must be default-active");

    require(m.sol("sol1").isEmpty() && m.sol("solmf").isEmpty(), "solutions must be empty");
    String eig = null;
    for (String f : m.sol("solmf").feature().tags())
      if (m.sol("solmf").feature(f).getType().equals("Eigenvalue")) eig = f;
    require(eig != null, "Eigenvalue solver");
    require("on".equals(m.sol("solmf").feature(eig).getString("modefollowing")),
        "solver Mode Following");
    boolean mf = false, eparam = false;
    for (String c : m.sol("solmf").feature(eig).feature().tags()) {
      String type = m.sol("solmf").feature(eig).feature(c).getType();
      mf |= type.equals("ModeFollowing");
      eparam |= type.equals("EigenvalueParam");
    }
    require(mf, "ModeFollowing solver attribute");
    require(!eparam, "duplicate EigenvalueParam with outer Parametric Sweep");
    require(m.result().tags().length == 0, "result list must be empty");
    ModelUtil.remove("VerifyBlochMF");
    System.out.println("BASE_VERIFY_FILE=" + path);
    System.out.println("BASE_VERIFY_STUDY=stdmf/[param,eig]");
    System.out.println("BASE_VERIFY_SOLUTIONS_EMPTY=true");
    System.out.println("BASE_VERIFY=PASS");
  }
}
