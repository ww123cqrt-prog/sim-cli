import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/**
 * Bounded numerical-readiness audit for the small asymmetric base model.
 * Solutions exist only in memory; the delivered MPH is never overwritten.
 */
public class VerifyBlochModeFollowingDenseConvergence {
  static final String MODEL = "COMSOL64_3D_Bloch_ModeFollowing_Base.mph";
  static final boolean EXTRACTION_SMOKE_ONLY = false;

  static String eigenvalueTag(Model m, String solution) throws Exception {
    for (String tag : m.sol(solution).feature().tags())
      if (m.sol(solution).feature(tag).getType().equals("Eigenvalue")) return tag;
    throw new Exception(solution + " Eigenvalue feature missing");
  }

  static double[][] runSweep(String name, int axis, String kList, int neigs,
      boolean refinedMesh) throws Exception {
    String tag = "Dense" + name.replaceAll("[^A-Za-z0-9]", "");
    long start = System.nanoTime();
    Model m = ModelUtil.load(tag, MODEL);
    m.param().set("use_k_scan", "1");
    m.param().set("path_mode", "2");
    m.param().set("path_axis", Integer.toString(axis));
    if (refinedMesh) {
      m.component("comp1").mesh("mesh1").feature("size1").set("hmax", "a/8");
      m.component("comp1").mesh("mesh1").feature("size1").set("hmin", "a/40");
      m.component("comp1").mesh("mesh1").run();
    }
    m.study("stdmf").feature("param").set("plistarr", new String[]{kList});
    m.study("stdmf").feature("eig").set("neigs", neigs);
    m.sol("solmf").feature(eigenvalueTag(m, "solmf")).set("neigs", neigs);
    m.study("stdmf").run();
    ArrayList<String> resultSolutions = new ArrayList<>();
    for (String solutionTag : m.sol().tags()) {
      boolean empty = m.sol(solutionTag).isEmpty();
      System.out.println("DENSE_SOL=" + name + " TAG=" + solutionTag + " EMPTY=" + empty);
      if (!empty) {
        System.out.println("DENSE_SOL_DATA=" + name + " TAG=" + solutionTag + " TYPE="
            + m.sol(solutionTag).getType() + " SEQUENCE_TYPE="
            + m.sol(solutionTag).getSequenceType() + " SIZE="
            + Arrays.toString(m.sol(solutionTag).getSize()) + " PARAM_NAMES="
            + Arrays.toString(m.sol(solutionTag).getParamNames()) + " PARAM_VALS="
            + Arrays.toString(m.sol(solutionTag).getParamVals()));
        if ("ParametricStore".equals(m.sol(solutionTag).getSequenceType()))
          resultSolutions.add(solutionTag);
      }
    }
    if (resultSolutions.isEmpty()) throw new Exception(name + " parametric stores are empty");
    String data = "auditdata", eval = "auditeval";
    m.result().dataset().create(data, "Solution");
    m.result().dataset(data).set("solution", resultSolutions.get(0));
    m.result().numerical().create(eval, "EvalGlobal");
    m.result().numerical(eval).set("data", data);
    m.result().numerical(eval).set("expr",
        new String[]{"k", "qx_active", "qy_active", "freq"});
    double[][] out = new double[5][resultSolutions.size() * neigs];
    int offset = 0;
    for (String storedSolution : resultSolutions) {
      double[] parameterValues = m.sol(storedSolution).getParamVals();
      if (parameterValues.length != 1)
        throw new Exception(name + " store " + storedSolution + " has unexpected parameters");
      m.result().dataset(data).set("solution", storedSolution);
      double[][] re = m.result().numerical(eval).getReal();
      double[][] im = m.result().numerical(eval).getImag();
      if (re.length != 4 || re[0].length != neigs || re[3].length != neigs)
        throw new Exception(name + " stored solution " + storedSolution
            + " unexpected EvalGlobal dimensions");
      for (int i = 0; i < neigs; i++) {
        out[0][offset] = parameterValues[0];
        out[1][offset] = re[1][i];
        out[2][offset] = re[2][i];
        out[3][offset] = re[3][i];
        out[4][offset] = im[3][i];
        offset++;
      }
    }
    double seconds = (System.nanoTime() - start) * 1e-9;
    int points = grouped(out).size();
    System.out.println("DENSE_RUN=" + name + " AXIS=" + axis + " NEIGS=" + neigs
        + " REFINED=" + refinedMesh + " POINTS=" + points + " VALUES=" + out[0].length
        + " SECONDS=" + seconds);
    ModelUtil.remove(tag);
    return out;
  }

  static TreeMap<Double, double[]> grouped(double[][] data) {
    TreeMap<Double, ArrayList<Double>> lists = new TreeMap<>();
    for (int i = 0; i < data[0].length; i++) {
      double key = Math.rint(data[0][i] * 1e12) / 1e12;
      lists.computeIfAbsent(key, unused -> new ArrayList<Double>());
      if (Double.isFinite(data[3][i]) && Double.isFinite(data[4][i]))
        lists.get(key).add(data[3][i]);
    }
    TreeMap<Double, double[]> out = new TreeMap<>();
    for (Map.Entry<Double, ArrayList<Double>> entry : lists.entrySet()) {
      double[] values = entry.getValue().stream().mapToDouble(Double::doubleValue).toArray();
      Arrays.sort(values);
      out.put(entry.getKey(), values);
    }
    return out;
  }

  static double nearestRelative(double value, double[] candidates) {
    double best = Double.POSITIVE_INFINITY;
    for (double candidate : candidates) {
      double scale = Math.max(Math.abs(value), Math.abs(candidate));
      best = Math.min(best, Math.abs(value - candidate) / scale);
    }
    return best;
  }

  static double compareSameCount(String label, double[][] a, double[][] b) throws Exception {
    TreeMap<Double, double[]> ga = grouped(a), gb = grouped(b);
    double maximum = 0;
    int compared = 0;
    int countMismatches = 0;
    for (Map.Entry<Double, double[]> entry : ga.entrySet()) {
      double[] bv = gb.get(entry.getKey());
      if (bv == null) continue;
      double[] av = entry.getValue();
      if (av.length != bv.length) countMismatches++;
      for (double value : av) maximum = Math.max(maximum, nearestRelative(value, bv));
      for (double value : bv) maximum = Math.max(maximum, nearestRelative(value, av));
      compared++;
    }
    if (compared == 0) throw new Exception(label + " has no common k points");
    System.out.println(label + "_COMMON_POINTS=" + compared);
    System.out.println(label + "_FINITE_COUNT_MISMATCH_POINTS=" + countMismatches);
    System.out.println(label + "_MAX_RELATIVE_NEAREST_FINITE_SPECTRUM_DIFFERENCE=" + maximum);
    return maximum;
  }

  static double compareContained(String label, double[][] reference, double[][] expanded)
      throws Exception {
    TreeMap<Double, double[]> a = grouped(reference), b = grouped(expanded);
    double maximum = 0;
    int compared = 0;
    int insufficientCandidatePoints = 0;
    for (Map.Entry<Double, double[]> entry : b.entrySet()) {
      double[] av = a.get(entry.getKey());
      if (av == null) continue;
      if (entry.getValue().length < av.length) insufficientCandidatePoints++;
      for (double value : av) maximum = Math.max(maximum,
          nearestRelative(value, entry.getValue()));
      compared++;
    }
    if (compared == 0) throw new Exception(label + " has no common k points");
    System.out.println(label + "_COMMON_POINTS=" + compared);
    System.out.println(label + "_INSUFFICIENT_CANDIDATE_POINTS=" + insufficientCandidatePoints);
    System.out.println(label + "_MAX_RELATIVE_NEAREST_SPECTRUM_DIFFERENCE=" + maximum);
    return maximum;
  }

  static int[] requireCounts(String label, double[][] data, int expectedPoints, int neigs)
      throws Exception {
    TreeMap<Double, double[]> groups = grouped(data);
    if (groups.size() != expectedPoints)
      throw new Exception(label + " expected " + expectedPoints + " points, got " + groups.size());
    int minimum = neigs, maximum = 0, stoppedPoints = 0;
    for (Map.Entry<Double, double[]> entry : groups.entrySet()) {
      int count = entry.getValue().length;
      minimum = Math.min(minimum, count);
      maximum = Math.max(maximum, count);
      if (count < neigs) stoppedPoints++;
    }
    System.out.println(label + "_FINITE_MODES_MIN=" + minimum);
    System.out.println(label + "_FINITE_MODES_MAX=" + maximum);
    System.out.println(label + "_POINTS_WITH_STOPPED_MODES=" + stoppedPoints);
    return new int[]{minimum, maximum, stoppedPoints};
  }

  public static void main(String[] args) throws Exception {
    if (EXTRACTION_SMOKE_ONLY) {
      double[][] smoke = runSweep("extraction_smoke", 0, "range(0,1,2)", 8, false);
      requireCounts("extraction_smoke", smoke, 3, 8);
      System.out.println("DENSE_EXTRACTION_SMOKE=PASS");
      return;
    }
    double[][] xf20 = runSweep("x_forward20", 0, "range(0,0.25,3)", 20, false);
    double[][] xr20 = runSweep("x_reverse20", 0, "range(3,-0.25,0)", 20, false);
    double[][] xc30 = runSweep("x_coarse30", 0, "range(0,0.5,3)", 30, false);
    double[][] xm20 = runSweep("x_refined20", 0, "range(0,0.5,3)", 20, true);
    double[][] yf20 = runSweep("y_forward20", 1, "range(0,0.25,3)", 20, false);
    double[][] yr20 = runSweep("y_reverse20", 1, "range(3,-0.25,0)", 20, false);
    double[][] yc30 = runSweep("y_coarse30", 1, "range(0,0.5,3)", 30, false);
    double[][] ym20 = runSweep("y_refined20", 1, "range(0,0.5,3)", 20, true);

    int[] xForwardCounts = requireCounts("x_forward20", xf20, 13, 20);
    requireCounts("x_reverse20", xr20, 13, 20);
    requireCounts("x_coarse30", xc30, 7, 30);
    requireCounts("x_refined20", xm20, 7, 20);
    int[] yForwardCounts = requireCounts("y_forward20", yf20, 13, 20);
    requireCounts("y_reverse20", yr20, 13, 20);
    requireCounts("y_coarse30", yc30, 7, 30);
    requireCounts("y_refined20", ym20, 7, 20);

    double xDirection = compareSameCount("X_FORWARD_REVERSE", xf20, xr20);
    double yDirection = compareSameCount("Y_FORWARD_REVERSE", yf20, yr20);
    double xCandidates = compareContained("X_20_IN_30", xf20, xc30);
    double yCandidates = compareContained("Y_20_IN_30", yf20, yc30);
    double xMesh = compareSameCount("X_BASE_REFINED_MESH", xf20, xm20);
    double yMesh = compareSameCount("Y_BASE_REFINED_MESH", yf20, ym20);
    System.out.println("DENSE_X_MESH_MEASURED=" + xMesh);
    System.out.println("DENSE_Y_MESH_MEASURED=" + yMesh);
    boolean complete = xForwardCounts[2] == 0 && yForwardCounts[2] == 0
        && xDirection <= 1e-9 && yDirection <= 1e-9
        && xCandidates <= 1e-8 && yCandidates <= 1e-8;
    System.out.println("DENSE_CONVERGENCE=" + (complete ? "PASS" : "PARTIAL"));
  }
}
