import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.File;
import java.util.*;

/**
 * Build an unsolved five-layer COMSOL 6.4 Bloch/Mode-Following base model
 * with a deliberately x/y-asymmetric rectangular inclusion for path tests.
 *
 * The visible Study tree owns the k sweep through a Parametric Sweep feature.
 * Mode Following is enabled on the Eigenfrequency step and Eigenvalue solver.
 * This class intentionally contains no study.run, sol.run, or runAll call.
 */
public class BuildBlochModeFollowingBase {
  static int[] ids(Collection<Integer> values) {
    return values.stream().mapToInt(Integer::intValue).toArray();
  }

  static int[] joinedIds(Collection<Integer> a, Collection<Integer> b) {
    return java.util.stream.IntStream.concat(a.stream().mapToInt(Integer::intValue),
        b.stream().mapToInt(Integer::intValue)).toArray();
  }

  static String outputPath() {
    return "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";
  }

  static void setParameters(Model m) {
    m.param().set("a", "1[um]", "Square primitive-cell pitch");
    m.param().set("lambda_ref", "1[um]", "Eigenfrequency shift wavelength");
    m.param().set("t_pml_bottom", "0.5[um]");
    m.param().set("t_substrate", "1[um]");
    m.param().set("t_structure", "0.5[um]");
    m.param().set("t_superstrate", "1[um]");
    m.param().set("t_pml_top", "0.5[um]");
    m.param().set("t_total",
        "t_pml_bottom+t_substrate+t_structure+t_superstrate+t_pml_top");
    m.param().set("n_bottom", "3.4", "Placeholder real substrate/PML index");
    m.param().set("n_structure", "3.4", "Placeholder real structure-layer index");
    m.param().set("n_pillar", "1.5", "Lossless asymmetric test-pillar index");
    m.param().set("n_top", "1", "Placeholder real superstrate/PML index");
    m.param().set("pillar_x", "0.46*a", "Asymmetric test-pillar x width");
    m.param().set("pillar_y", "0.22*a", "Asymmetric test-pillar y width");
    m.param().set("qx", "0", "Manual reduced Bloch coordinate x; set use_k_scan=0");
    m.param().set("qy", "0", "Manual reduced Bloch coordinate y; set use_k_scan=0");
    m.param().set("k", "0", "Dimensionless ordered path coordinate");
    m.param().set("use_k_scan", "1", "1: use k path; 0: use manual qx/qy");
    m.param().set("path_mode", "2",
        "0: q=(k,0); 1: Gamma-X-M-Gamma; 2: M-Gamma-X/Y-M selected by path_axis");
    m.param().set("path_axis", "0", "For path_mode=2: 0 selects X, 1 selects Y");
    m.param().set("qx_scan",
        "if(path_mode<0.5,k,if(path_mode<1.5,if(k<=1,0.5*k,if(k<=2,0.5,0.5*(3-k))),if(k<=1,0.5*(1-k),if(k<=2,if(path_axis<0.5,0.5*(k-1),0),if(path_axis<0.5,0.5,0.5*(k-2))))))");
    m.param().set("qy_scan",
        "if(path_mode<0.5,0,if(path_mode<1.5,if(k<=1,0,if(k<=2,0.5*(k-1),0.5*(3-k))),if(k<=1,0.5*(1-k),if(k<=2,if(path_axis<0.5,0,0.5*(k-1)),if(path_axis<0.5,0.5*(k-2),0.5)))))");
    m.param().set("qx_active", "if(use_k_scan>0.5,qx_scan,qx)");
    m.param().set("qy_active", "if(use_k_scan>0.5,qy_scan,qy)");
    m.param().set("kBx", "2*pi*qx_active/a", "Physical Floquet wavevector x in rad/m");
    m.param().set("kBy", "2*pi*qy_active/a", "Physical Floquet wavevector y in rad/m");
    m.param().set("periodic_x_dx", "a");
    m.param().set("periodic_y_dy", "a");
    m.param().set("floquet_phase_x", "exp(-i*kBx*periodic_x_dx)");
    m.param().set("floquet_phase_y", "exp(-i*kBy*periodic_y_dy)");
  }

  static List<Integer>[] sideFaces(Model m, double aMeters) throws Exception {
    @SuppressWarnings("unchecked")
    List<Integer>[] out = new List[]{new ArrayList<Integer>(), new ArrayList<Integer>(),
        new ArrayList<Integer>(), new ArrayList<Integer>()};
    int nb = m.component("comp1").geom("geom1").getNBoundaries();
    double tol = Math.max(2e-12, 1e-6 * aMeters);
    for (int b = 1; b <= nb; b++) {
      m.component("comp1").geom("geom1").measureFinal().selection().geom(2);
      m.component("comp1").geom("geom1").measureFinal().selection().set(b);
      double[] box = m.component("comp1").geom("geom1").measureFinal().getBoundingBox();
      if (Math.abs(box[1] - box[0]) < tol && Math.abs(box[0] + aMeters / 2.0) < tol) out[0].add(b);
      if (Math.abs(box[1] - box[0]) < tol && Math.abs(box[0] - aMeters / 2.0) < tol) out[1].add(b);
      if (Math.abs(box[3] - box[2]) < tol && Math.abs(box[2] + aMeters / 2.0) < tol) out[2].add(b);
      if (Math.abs(box[3] - box[2]) < tol && Math.abs(box[2] - aMeters / 2.0) < tol) out[3].add(b);
    }
    for (List<Integer> f : out) if (f.isEmpty()) throw new Exception("empty periodic side selection");
    return out;
  }

  static void createFloquetBoundaryConditions(Model m) throws Exception {
    List<Integer>[] s = sideFaces(m, 1e-6);
    // Do not create unused Identity pairs. EWFD's default pair continuity
    // consumes them and can impose an unintended mesh-mapping constraint.
    m.component("comp1").physics("ewfd").create("pcx", "PeriodicCondition", 2);
    m.component("comp1").physics("ewfd").feature("pcx").label(
        "Floquet x: -x source to +x manual destination");
    m.component("comp1").physics("ewfd").feature("pcx").selection().set(joinedIds(s[0], s[1]));
    m.component("comp1").physics("ewfd").feature("pcx").set("manualDestinationSelection", true);
    m.component("comp1").physics("ewfd").feature("pcx").selection("destinationDomains").set(ids(s[1]));
    m.component("comp1").physics("ewfd").feature("pcx").set("PeriodicType", "Floquet");
    m.component("comp1").physics("ewfd").feature("pcx").set("Floquet_source", "UserDefined");
    m.component("comp1").physics("ewfd").feature("pcx").set("kFloquet",
        new String[]{"kBx", "kBy", "0"});

    m.component("comp1").physics("ewfd").create("pcy", "PeriodicCondition", 2);
    m.component("comp1").physics("ewfd").feature("pcy").label(
        "Floquet y: -y source to +y manual destination");
    m.component("comp1").physics("ewfd").feature("pcy").selection().set(joinedIds(s[2], s[3]));
    m.component("comp1").physics("ewfd").feature("pcy").set("manualDestinationSelection", true);
    m.component("comp1").physics("ewfd").feature("pcy").selection("destinationDomains").set(ids(s[3]));
    m.component("comp1").physics("ewfd").feature("pcy").set("PeriodicType", "Floquet");
    m.component("comp1").physics("ewfd").feature("pcy").set("Floquet_source", "UserDefined");
    m.component("comp1").physics("ewfd").feature("pcy").set("kFloquet",
        new String[]{"kBx", "kBy", "0"});
  }

  static String eigenvalueTag(Model m, String solution) throws Exception {
    for (String f : m.sol(solution).feature().tags())
      if (m.sol(solution).feature(f).getType().equals("Eigenvalue")) return f;
    throw new Exception(solution + " lacks Eigenvalue solver");
  }

  static void configureStudies(Model m) throws Exception {
    m.study().create("std1");
    m.study("std1").label("Manual single Bloch point: set use_k_scan=0, qx, qy");
    m.study("std1").create("eig", "Eigenfrequency");
    m.study("std1").feature("eig").set("neigsactive", true);
    m.study("std1").feature("eig").set("neigs", 20);
    m.study("std1").feature("eig").set("shift", "c_const/lambda_ref");
    m.sol().create("sol1");
    m.sol("sol1").createAutoSequence("std1");

    m.study().create("stdmf");
    m.study("stdmf").label("Visible k Parametric Sweep with COMSOL 6.4 Mode Following");
    m.study("stdmf").create("param", "Parametric");
    m.study("stdmf").feature("param").label("k sweep: M-Gamma-X/Y-M demonstration");
    m.study("stdmf").feature("param").set("pname", new String[]{"k"});
    m.study("stdmf").feature("param").set("plistarr",
        new String[]{"range(0,0.25,3)"});
    m.study("stdmf").feature("param").set("punit", new String[]{""});
    m.study("stdmf").feature("param").set("sweeptype", "sparse");
    m.study("stdmf").feature("param").set("pdistrib", "off");
    m.study("stdmf").create("eig", "Eigenfrequency");
    m.study("stdmf").feature("eig").set("neigsactive", true);
    m.study("stdmf").feature("eig").set("neigs", 20);
    m.study("stdmf").feature("eig").set("shift", "c_const/lambda_ref");
    m.study("stdmf").feature("eig").set("modefollowing", true);
    m.sol().create("solmf");
    m.sol("solmf").createAutoSequence("stdmf");

    String eig = eigenvalueTag(m, "solmf");
    m.sol("solmf").feature(eig).set("modefollowing", "on");
    m.sol("solmf").feature(eig).set("neigs", 20);
    m.sol("solmf").feature(eig).set("shift", "c_const/lambda_ref");
    m.sol("solmf").feature(eig).set("stopwhennoeigfound", "on");
    String mf = null;
    for (String c : m.sol("solmf").feature(eig).feature().tags()) {
      String type = m.sol("solmf").feature(eig).feature(c).getType();
      if (type.equals("EigenvalueParam"))
        throw new Exception("duplicate sweep owner: outer Parametric Sweep plus EigenvalueParam");
      if (type.equals("ModeFollowing")) mf = c;
    }
    if (mf == null) {
      mf = "mf1";
      m.sol("solmf").feature(eig).create(mf, "ModeFollowing");
    }
    m.sol("solmf").feature(eig).feature(mf).set("detectifcannotfollowpreviousmodes", "on");
    m.sol("solmf").feature(eig).feature(mf).set("thresholdmodefollowing", 0.01);
    m.sol("solmf").feature(eig).feature(mf).set("highsenseigdetection", "off");
    m.sol("solmf").feature(eig).feature(mf).set("followextramodes", "off");
  }

  static Model build() throws Exception {
    String out = outputPath();
    Model m = ModelUtil.create("BlochModeFollowingBase");
    m.label("COMSOL64_3D_Bloch_ModeFollowing_Base.mph");
    setParameters(m);

    m.component().create("comp1", true);
    m.component("comp1").geom().create("geom1", 3);
    m.component("comp1").geom("geom1").create("stack", "Block");
    m.component("comp1").geom("geom1").feature("stack").set("base", "center");
    m.component("comp1").geom("geom1").feature("stack").set("size",
        new String[]{"a", "a", "t_total"});
    m.component("comp1").geom("geom1").feature("stack").set("pos", new String[]{"0", "0", "0"});
    m.component("comp1").geom("geom1").feature("stack").setIndex("layer", "t_pml_bottom", 0);
    m.component("comp1").geom("geom1").feature("stack").setIndex("layer", "t_substrate", 1);
    m.component("comp1").geom("geom1").feature("stack").setIndex("layer", "t_structure", 2);
    m.component("comp1").geom("geom1").feature("stack").setIndex("layer", "t_superstrate", 3);
    m.component("comp1").geom("geom1").create("pillar", "Block");
    m.component("comp1").geom("geom1").feature("pillar").label(
        "Asymmetric rectangular validation pillar");
    m.component("comp1").geom("geom1").feature("pillar").set("base", "center");
    m.component("comp1").geom("geom1").feature("pillar").set("size",
        new String[]{"pillar_x", "pillar_y", "t_total"});
    m.component("comp1").geom("geom1").feature("pillar").set("pos",
        new String[]{"0", "0", "0"});
    m.component("comp1").geom("geom1").run();

    int nd = m.component("comp1").geom("geom1").getNDomains();
    // The partition column crosses the complete stack so every z layer has the
    // same 2-D topology and remains sweep-meshable.  Only its central segment
    // receives n_pillar; the four other inner segments keep their host index.
    if (nd != 10) throw new Exception("expected two sweep-compatible domains per layer, got " + nd);
    List<Integer> ordered = new ArrayList<>();
    Map<Integer, Double> zmid = new HashMap<>();
    Map<Integer, double[]> domainBoxes = new HashMap<>();
    for (int d = 1; d <= nd; d++) {
      m.component("comp1").geom("geom1").measureFinal().selection().geom(3);
      m.component("comp1").geom("geom1").measureFinal().selection().set(d);
      double[] box = m.component("comp1").geom("geom1").measureFinal().getBoundingBox();
      ordered.add(d);
      zmid.put(d, 0.5 * (box[4] + box[5]));
      domainBoxes.put(d, box);
    }
    ordered.sort(Comparator.comparingDouble(zmid::get));
    int[][] layers = new int[5][2]; // [layer][0 inner, 1 outer]
    for (int layer = 0; layer < 5; layer++) {
      int da = ordered.get(2 * layer), db = ordered.get(2 * layer + 1);
      double[] ba = domainBoxes.get(da), bb = domainBoxes.get(db);
      double areaA = (ba[1] - ba[0]) * (ba[3] - ba[2]);
      double areaB = (bb[1] - bb[0]) * (bb[3] - bb[2]);
      layers[layer][0] = areaA < areaB ? da : db;
      layers[layer][1] = areaA < areaB ? db : da;
    }
    int dPillar = layers[2][0], dStruct = layers[2][1];

    m.component("comp1").material().create("matbottom", "Common");
    m.component("comp1").material("matbottom").label("Placeholder bottom medium");
    m.component("comp1").material("matbottom").selection().set(
        layers[0][0], layers[0][1], layers[1][0], layers[1][1]);
    m.component("comp1").material("matbottom").propertyGroup().create(
        "RefractiveIndex", "RefractiveIndex", "Refractive index");
    m.component("comp1").material("matbottom").propertyGroup("RefractiveIndex").set(
        "n", new String[]{"n_bottom"});
    m.component("comp1").material().create("matstructure", "Common");
    m.component("comp1").material("matstructure").label("Placeholder structure layer");
    m.component("comp1").material("matstructure").selection().set(dStruct);
    m.component("comp1").material("matstructure").propertyGroup().create(
        "RefractiveIndex", "RefractiveIndex", "Refractive index");
    m.component("comp1").material("matstructure").propertyGroup("RefractiveIndex").set(
        "n", new String[]{"n_structure"});
    m.component("comp1").material().create("matpillar", "Common");
    m.component("comp1").material("matpillar").label(
        "Lossless asymmetric validation pillar");
    m.component("comp1").material("matpillar").selection().set(dPillar);
    m.component("comp1").material("matpillar").propertyGroup().create(
        "RefractiveIndex", "RefractiveIndex", "Refractive index");
    m.component("comp1").material("matpillar").propertyGroup("RefractiveIndex").set(
        "n", new String[]{"n_pillar"});
    m.component("comp1").material().create("mattop", "Common");
    m.component("comp1").material("mattop").label("Placeholder top medium");
    m.component("comp1").material("mattop").selection().set(
        layers[3][0], layers[3][1], layers[4][0], layers[4][1]);
    m.component("comp1").material("mattop").propertyGroup().create(
        "RefractiveIndex", "RefractiveIndex", "Refractive index");
    m.component("comp1").material("mattop").propertyGroup("RefractiveIndex").set(
        "n", new String[]{"n_top"});

    m.component("comp1").coordSystem().create("pmlbot", "PML");
    m.component("comp1").coordSystem("pmlbot").selection().set(
        layers[0][0], layers[0][1]);
    m.component("comp1").coordSystem().create("pmltop", "PML");
    m.component("comp1").coordSystem("pmltop").selection().set(
        layers[4][0], layers[4][1]);

    m.component("comp1").physics().create("ewfd", "ElectromagneticWavesFrequencyDomain", "geom1");
    m.component("comp1").physics("ewfd").prop("ShapeProperty").set("order_electricfield", 2);
    createFloquetBoundaryConditions(m);

    List<Integer> bottomFaces = new ArrayList<>();
    int nb = m.component("comp1").geom("geom1").getNBoundaries();
    double zMin = Double.POSITIVE_INFINITY;
    Map<Integer, double[]> boxes = new HashMap<>();
    for (int b = 1; b <= nb; b++) {
      m.component("comp1").geom("geom1").measureFinal().selection().geom(2);
      m.component("comp1").geom("geom1").measureFinal().selection().set(b);
      double[] box = m.component("comp1").geom("geom1").measureFinal().getBoundingBox();
      boxes.put(b, box);
      zMin = Math.min(zMin, box[4]);
    }
    for (int b = 1; b <= nb; b++) {
      double[] box = boxes.get(b);
      if (Math.abs(box[5] - box[4]) < 1e-12 && Math.abs(box[4] - zMin) < 1e-12)
        bottomFaces.add(b);
    }
    m.component("comp1").mesh().create("mesh1");
    m.component("comp1").mesh("mesh1").create("size1", "Size");
    m.component("comp1").mesh("mesh1").feature("size1").set("custom", "on");
    m.component("comp1").mesh("mesh1").feature("size1").set("hmax", "a/6");
    m.component("comp1").mesh("mesh1").feature("size1").set("hmin", "a/30");
    m.component("comp1").mesh("mesh1").create("ftri1", "FreeTri");
    m.component("comp1").mesh("mesh1").feature("ftri1").label(
        "Free triangular source mesh for sweep-compatible column");
    m.component("comp1").mesh("mesh1").feature("ftri1").selection().set(ids(bottomFaces));
    m.component("comp1").mesh("mesh1").create("swe1", "Sweep");
    m.component("comp1").mesh("mesh1").feature("swe1").selection().geom(3);
    m.component("comp1").mesh("mesh1").feature("swe1").selection().all();
    m.component("comp1").mesh("mesh1").run();

    configureStudies(m);
    m.save(out);
    System.out.println("BASE_FILE=" + out);
    System.out.println("BASE_DOMAINS=" + nd + " BASE_BOUNDARIES=" + nb
        + " BASE_ELEMENTS=" + m.component("comp1").mesh("mesh1").getNumElem());
    System.out.println("BASE_SOL1_EMPTY=" + m.sol("sol1").isEmpty());
    System.out.println("BASE_SOLMF_EMPTY=" + m.sol("solmf").isEmpty());
    System.out.println("BASE_BUILD=PASS");
    return m;
  }

  public static void main(String[] args) throws Exception { build(); }
}
