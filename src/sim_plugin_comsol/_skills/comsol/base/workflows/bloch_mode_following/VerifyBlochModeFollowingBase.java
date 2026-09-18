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

  static void anchor(Model m, int axis, double pathK, double qx, double qy)
      throws Exception {
    m.param().set("path_mode", "2");
    m.param().set("path_axis", Integer.toString(axis));
    m.param().set("k", Double.toString(pathK));
    double actualQx = m.param().evaluate("qx_scan");
    double actualQy = m.param().evaluate("qy_scan");
    require(Math.abs(actualQx - qx) < 1e-14 && Math.abs(actualQy - qy) < 1e-14,
        "dual-path anchor axis=" + axis + " k=" + pathK + " got ("
            + actualQx + "," + actualQy + ")");
  }

  public static void main(String[] args) throws Exception {
    String path = modelPath();
    Model m = ModelUtil.load("VerifyBlochMF", path);
    require(ModelUtil.getComsolVersion().startsWith("COMSOL Multiphysics 6.4"), "COMSOL version");
    require(m.component("comp1").geom("geom1").getNDomains() == 10,
        "sweep-compatible two-domain partition in each of five layers");
    require(has(m.component("comp1").material().tags(), "matpillar"),
        "asymmetric-pillar material");
    require("2".equals(m.param().get("path_mode")), "dual-path mode must be default-active");
    require("0".equals(m.param().get("path_axis")), "X path must be the default axis");
    require(m.param().get("qx_scan").contains("path_axis"), "qx dual-path expression");
    require(m.param().get("qy_scan").contains("path_axis"), "qy dual-path expression");
    require(m.param().evaluate("pillar_x") > m.param().evaluate("pillar_y"),
        "pillar must deliberately break x/y interchange symmetry");
    anchor(m, 0, 0, 0.5, 0.5);
    anchor(m, 0, 1, 0, 0);
    anchor(m, 0, 2, 0.5, 0);
    anchor(m, 0, 3, 0.5, 0.5);
    anchor(m, 1, 0, 0.5, 0.5);
    anchor(m, 1, 1, 0, 0);
    anchor(m, 1, 2, 0, 0.5);
    anchor(m, 1, 3, 0.5, 0.5);
    m.param().set("path_axis", "0");
    m.param().set("k", "0");
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
    require(m.study("stdmf").label().contains("EXPERIMENTAL / UNSTABLE"),
        "Mode Following study must be visibly marked experimental and unstable");
    require(has(m.study("stdmf").feature().tags(), "param"),
        "visible Parametric Sweep study step missing");
    require("Parametric".equals(m.study("stdmf").feature("param").getType()),
        "param feature type");
    require("k".equals(m.study("stdmf").feature("param").getString("pname")),
        "swept parameter must be k");
    String parameterList = m.study("stdmf").feature("param").getString("plistarr");
    System.out.println("BASE_VERIFY_PARAMETER_LIST=" + parameterList);
    require(parameterList.contains("0") && parameterList.contains("0.25")
        && parameterList.contains("3"),
        "default M-Gamma-X/Y-M demonstration sweep");
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
    boolean mf = false, eparam = false, unstableLabel = false;
    for (String c : m.sol("solmf").feature(eig).feature().tags()) {
      String type = m.sol("solmf").feature(eig).feature(c).getType();
      mf |= type.equals("ModeFollowing");
      if (type.equals("ModeFollowing"))
        unstableLabel |= m.sol("solmf").feature(eig).feature(c).label()
            .contains("EXPERIMENTAL / UNSTABLE");
      eparam |= type.equals("EigenvalueParam");
    }
    require(mf, "ModeFollowing solver attribute");
    require(unstableLabel, "ModeFollowing solver node must carry unstable label");
    require(!eparam, "duplicate EigenvalueParam with outer Parametric Sweep");
    require(m.result().tags().length == 0, "result list must be empty");
    ModelUtil.remove("VerifyBlochMF");
    System.out.println("BASE_VERIFY_FILE=" + path);
    System.out.println("BASE_VERIFY_STUDY=stdmf/[param,eig]");
    System.out.println("BASE_VERIFY_SOLUTIONS_EMPTY=true");
    System.out.println("BASE_VERIFY=PASS");
  }
}
